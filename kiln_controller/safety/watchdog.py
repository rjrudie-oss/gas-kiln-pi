"""Independent fail-safe watchdog process.

This runs as a SEPARATE process (and a separate systemd unit) from the control
loop. Its only responsibility is: if the controller stops proving it is alive,
force the gas valve closed.

Why a separate process? If the control loop freezes (deadlock, infinite loop,
GC pause, Python crash), it cannot close its own valve. An independent process
whose sole job is to watch the heartbeat and slam the valve shut is far more
trustworthy. On a Pi you would additionally enable the hardware watchdog timer
so that even a kernel/OS freeze reboots the board — see SAFETY.md.

Fail-safe logic:
  * No heartbeat file / stale heartbeat  -> close valve.
  * Any exception while reading it        -> close valve.
  * On shutdown (SIGTERM/SIGINT)          -> close valve.
"""
from __future__ import annotations

import logging
import signal
import time
from typing import Optional

from ..config import Config
from ..hardware import make_valve
from ..hardware.valve import GasValve, RelayValve
from .heartbeat import Heartbeat

log = logging.getLogger("kiln.watchdog")


def _make_watchdog_valve(cfg: Config) -> GasValve:
    """Build the actuator the watchdog controls.

    Prefer a dedicated cutoff relay on ``watchdog_relay_gpio`` so the watchdog
    never contends with the controller for the main relay GPIO. If none is
    configured, fall back to the standard valve (only safe when the controller
    is not running on the same pin).
    """
    hw = cfg.hardware
    if not hw.simulate and hw.watchdog_relay_gpio >= 0:
        return RelayValve(
            gpio=hw.watchdog_relay_gpio,
            active_high=hw.valve_relay_active_high,
            window_s=hw.valve_pwm_window_s,
        )
    return make_valve(hw)


class Watchdog:
    def __init__(self, cfg: Config, valve: Optional[GasValve] = None) -> None:
        self.cfg = cfg
        self.valve = valve or _make_watchdog_valve(cfg)
        self.heartbeat = Heartbeat(cfg.safety.heartbeat_path)
        self._running = False
        self._valve_open_seen = False

    def _close(self, reason: str) -> None:
        try:
            self.valve.close()
        finally:
            log.warning("watchdog forced valve CLOSED: %s", reason)

    def step(self) -> bool:
        """One check. Returns True if the controller is proven alive."""
        try:
            age = self.heartbeat.age()
        except Exception as exc:  # pragma: no cover - defensive
            self._close(f"error reading heartbeat: {exc}")
            return False

        if age is None:
            self._close("no heartbeat file")
            return False
        if age > self.cfg.safety.heartbeat_timeout_s:
            self._close(f"heartbeat stale ({age:.1f}s)")
            return False
        return True

    def run(self) -> None:
        self._running = True
        self._install_signal_handlers()
        # Start from a known-safe state.
        self._close("watchdog startup")
        log.info(
            "watchdog started; heartbeat=%s timeout=%.1fs",
            self.cfg.safety.heartbeat_path,
            self.cfg.safety.heartbeat_timeout_s,
        )
        interval = max(0.1, self.cfg.safety.heartbeat_interval_s / 2.0)
        while self._running:
            self.step()
            time.sleep(interval)
        self._close("watchdog stopping")

    def stop(self, *_args) -> None:
        self._running = False

    def _install_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)


def main(argv: Optional[list] = None) -> int:
    import argparse

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="Kiln fail-safe watchdog")
    parser.add_argument("-c", "--config", default=None, help="path to config.yaml")
    args = parser.parse_args(argv)
    cfg = Config.load(args.config)
    Watchdog(cfg).run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
