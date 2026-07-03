"""Gas valve drivers.

FAIL-SAFE CONVENTION
--------------------
0 % command == valve closed / gas off. Every code path that cannot prove it is
safe to feed gas drives the valve to 0 %. ``close()`` is the strongest form.

Two driver styles are provided:

``RelayValve`` (default for this build)
    Time-proportional (slow-PWM) on/off control of a **normally-closed 12 V
    solenoid** switched by a relay channel (e.g. SainSmart 4-ch). The PID's
    0-100 % output is a duty cycle over a fixed window (e.g. 10 s), so 30 %
    means the solenoid is open for 3 s of every 10 s. Wiring is arranged so a
    de-energized relay leaves the (normally-closed) solenoid shut -> gas off is
    the default at power-up and on any fault.

``MCP4725Valve`` (analog option, not used by the current parts list)
    Drives a motorized *modulating* valve with a 0-10 V analog signal from an
    MCP4725 DAC + gain stage. Kept for a future proportional-valve upgrade.
"""
from __future__ import annotations

import time
from typing import Optional, Protocol


class GasValve(Protocol):
    def set_percent(self, percent: float) -> None: ...
    def close(self) -> None: ...
    @property
    def commanded_percent(self) -> float: ...


def _clamp_percent(percent: float) -> float:
    if percent != percent:  # NaN
        return 0.0
    return max(0.0, min(100.0, float(percent)))


class RelayValve:
    """Time-proportional (slow-PWM) on/off control of a solenoid via a relay.

    ``gpio`` is the BCM pin driving the relay channel. ``active_high`` reflects
    the relay board's logic: many boards (incl. SainSmart) are active-LOW, i.e.
    a LOW output energizes the coil. Regardless of that, the relay contacts are
    wired so the (normally-closed) solenoid is CLOSED when the coil is
    de-energized, so power-up and any fault default to gas-off.

    ``window_s`` is the PWM period. With a 1 s control loop and a 10 s window
    the effective duty resolution is 10 %.
    """

    def __init__(
        self,
        gpio: int,
        active_high: bool = True,
        window_s: float = 10.0,
        min_on_fraction: float = 0.02,
    ) -> None:
        import gpiozero  # type: ignore

        self._window_s = max(1.0, window_s)
        self._min_on = min_on_fraction
        self._commanded = 0.0
        self._window_start = time.monotonic()
        # initial_value=False -> starts de-energized -> gas off.
        self._relay = gpiozero.OutputDevice(
            gpio, active_high=active_high, initial_value=False
        )

    def _apply(self, now: Optional[float] = None) -> None:
        now = now if now is not None else time.monotonic()
        duty = self._commanded / 100.0
        if duty <= self._min_on:
            self._relay.off()
            return
        if duty >= 1.0 - self._min_on:
            self._relay.on()
            return
        phase = (now - self._window_start) % self._window_s
        if phase < duty * self._window_s:
            self._relay.on()
        else:
            self._relay.off()

    def set_percent(self, percent: float) -> None:
        self._commanded = _clamp_percent(percent)
        self._apply()

    def close(self) -> None:
        self._commanded = 0.0
        self._relay.off()

    @property
    def commanded_percent(self) -> float:
        return self._commanded


class MCP4725Valve:
    """Real valve driver backed by the Adafruit MCP4725 driver (lazy import)."""

    def __init__(
        self,
        i2c_bus: int = 1,
        address: int = 0x60,
        dac_vref: float = 5.0,
        valve_full_scale_v: float = 10.0,
        power_gpio: int = -1,
    ) -> None:
        import board  # type: ignore
        import busio  # type: ignore
        import adafruit_mcp4725  # type: ignore

        i2c = busio.I2C(board.SCL, board.SDA)
        self._dac = adafruit_mcp4725.MCP4725(i2c, address=address)
        self._vref = dac_vref
        self._full_scale_v = valve_full_scale_v
        self._commanded = 0.0
        self._power = None
        if power_gpio >= 0:
            import digitalio  # type: ignore

            self._power = digitalio.DigitalInOut(getattr(board, f"D{power_gpio}"))
            self._power.direction = digitalio.Direction.OUTPUT
            self._power.value = False  # start de-energized
        # Start closed no matter what.
        self.close()

    def set_percent(self, percent: float) -> None:
        percent = _clamp_percent(percent)
        if self._power is not None and percent > 0.0:
            self._power.value = True
        # Convert a 0-100 % valve command into the DAC's 0-1 normalized output.
        # The op-amp gain maps 0-Vref at the DAC to 0-full_scale_v at the valve,
        # so the DAC fraction that yields ``percent`` of full scale is linear.
        self._dac.normalized_value = percent / 100.0
        self._commanded = percent

    def close(self) -> None:
        self._dac.normalized_value = 0.0
        self._commanded = 0.0
        if self._power is not None:
            self._power.value = False

    @property
    def commanded_percent(self) -> float:
        return self._commanded


class SimulatedValve:
    """In-memory valve used for simulation, CI and tests.

    If a :class:`SimulatedThermocouple` is attached via :meth:`bind_thermocouple`
    the commanded position drives the simulated kiln, closing the control loop.
    """

    def __init__(self, full_scale_v: float = 10.0) -> None:
        self._full_scale_v = full_scale_v
        self._commanded = 0.0
        self._thermocouple = None

    def bind_thermocouple(self, thermocouple) -> None:
        self._thermocouple = thermocouple

    def set_percent(self, percent: float) -> None:
        self._commanded = _clamp_percent(percent)
        if self._thermocouple is not None:
            self._thermocouple.set_valve_fraction(self._commanded / 100.0)

    def close(self) -> None:
        self.set_percent(0.0)

    @property
    def commanded_percent(self) -> float:
        return self._commanded

    @property
    def commanded_voltage(self) -> float:
        return self._commanded / 100.0 * self._full_scale_v
