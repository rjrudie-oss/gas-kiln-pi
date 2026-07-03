"""Main PID control loop for the gas kiln.

Each iteration:
  1. Read the thermocouple.
  2. Run safety limit checks. If any trip, force the valve closed and skip PID.
  3. Otherwise compute the scheduled setpoint from the firing profile and run
     the PID to get a valve command.
  4. Drive the valve.
  5. Update the heartbeat and publish state for the dashboard.

Fail-safe guarantees:
  * ANY unhandled exception in the loop closes the valve before re-raising or
    retrying.
  * On shutdown (SIGTERM/SIGINT) the valve is closed.
  * The valve is never left open when a safety limit is tripped.
"""
from __future__ import annotations

import logging
import os
import signal
import time
from typing import Optional

from .config import Config
from .control.pid import PID
from .control.profile import FiringProfile
from .hardware import make_thermocouple, make_valve
from .hardware.thermocouple import SimulatedThermocouple, Thermocouple
from .hardware.valve import GasValve, SimulatedValve
from .safety.heartbeat import Heartbeat
from .safety.limits import SafetyLimits
from .state import KilnState, write_state

log = logging.getLogger("kiln.controller")


class KilnController:
    def __init__(
        self,
        cfg: Config,
        thermocouple: Optional[Thermocouple] = None,
        valve: Optional[GasValve] = None,
        state_path: str = "/run/kiln/state.json",
    ) -> None:
        self.cfg = cfg
        self.thermocouple = thermocouple or make_thermocouple(cfg.hardware)
        self.valve = valve or make_valve(cfg.hardware)
        self.state_path = state_path

        # Wire the simulated valve to the simulated sensor so the loop closes.
        if isinstance(self.valve, SimulatedValve) and isinstance(
            self.thermocouple, SimulatedThermocouple
        ):
            self.valve.bind_thermocouple(self.thermocouple)

        self.pid = PID(
            kp=cfg.pid.kp,
            ki=cfg.pid.ki,
            kd=cfg.pid.kd,
            output_min=cfg.pid.output_min,
            output_max=cfg.pid.output_max,
            integral_limit=cfg.pid.integral_limit,
        )
        self.limits = SafetyLimits(cfg.safety)
        self.heartbeat = Heartbeat(cfg.safety.heartbeat_path)
        self.profile = FiringProfile.from_tuples(cfg.control.profile)

        self._running = False
        self._last_ts: Optional[float] = None

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        self._running = True
        self.pid.reset()
        self.limits.reset()

    def stop(self, *_args) -> None:
        self._running = False

    def _install_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

    def _safe_shutdown(self, reason: str) -> None:
        try:
            self.valve.close()
        finally:
            log.warning("controller closed valve: %s", reason)

    # -- one iteration -----------------------------------------------------
    def tick(self, now: Optional[float] = None) -> KilnState:
        now = now if now is not None else time.time()
        dt = self.cfg.control.loop_interval_s
        if self._last_ts is not None:
            dt = max(1e-3, now - self._last_ts)
        self._last_ts = now

        state = KilnState(timestamp=now, running=self._running)

        try:
            reading = self.thermocouple.read()
            state.temperature_c = None if reading.fault else reading.temperature_c

            # Software emergency stop: presence of the e-stop file forces closed.
            if os.path.exists(self.cfg.safety.estop_path):
                self.valve.close()
                state.valve_percent = 0.0
                state.safe_state = True
                state.fault = "emergency stop engaged"
                state.message = "SAFE STATE: emergency stop engaged"
                self.pid.reset()
                return state

            limit = self.limits.check(reading, now)
            if not limit.safe:
                self.valve.close()
                state.valve_percent = 0.0
                state.safe_state = True
                state.fault = limit.reason
                state.message = f"SAFE STATE: {limit.reason}"
                log.warning("safety limit tripped: %s", limit.reason)
                return state

            # Advance the firing schedule and compute the setpoint.
            self.profile.advance(dt)
            setpoint = self.profile.setpoint()
            output = self.pid.update(setpoint, reading.temperature_c, dt)

            self.valve.set_percent(output)

            state.setpoint_c = setpoint
            state.pid_output = output
            state.valve_percent = self.valve.commanded_percent
            state.valve_voltage = getattr(self.valve, "commanded_voltage", None)
            state.safe_state = False
            state.profile_elapsed_s = self.profile.elapsed_s
            state.profile_finished = self.profile.finished
            state.message = "running"
            return state
        except Exception as exc:  # fail safe on ANY error
            self._safe_shutdown(f"exception in control loop: {exc}")
            state.valve_percent = 0.0
            state.safe_state = True
            state.fault = str(exc)
            state.message = f"SAFE STATE (exception): {exc}"
            log.exception("control loop exception")
            return state

    # -- main loop ---------------------------------------------------------
    def run(self) -> None:
        self._install_signal_handlers()
        self.start()
        # Known-safe starting point.
        self._safe_shutdown("controller startup")
        log.info("controller started (simulate=%s)", self.cfg.hardware.simulate)
        try:
            while self._running:
                state = self.tick()
                self.heartbeat.beat()
                try:
                    write_state(self.state_path, state)
                except Exception:  # dashboard IO must never stop the loop
                    log.exception("failed to write state (continuing)")
                time.sleep(self.cfg.control.loop_interval_s)
        finally:
            self._safe_shutdown("controller stopping")


def main(argv: Optional[list] = None) -> int:
    import argparse

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="Gas kiln PID controller")
    parser.add_argument("-c", "--config", default=None, help="path to config.yaml")
    parser.add_argument(
        "--state-path", default="/run/kiln/state.json", help="state snapshot path"
    )
    args = parser.parse_args(argv)
    cfg = Config.load(args.config)
    KilnController(cfg, state_path=args.state_path).run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
