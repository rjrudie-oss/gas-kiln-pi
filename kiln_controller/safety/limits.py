"""In-loop safety limit checks.

These run *inside* the control loop on every iteration and are the first line
of defence. They are intentionally independent of the PID math: even a perfectly
behaved PID output is overridden if any limit trips. On a trip the valve is
forced to 0 % (closed).

Note: these software checks are on top of — never a replacement for — the
external certified flame-safeguard hardware that proves flame and cuts gas.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..config import SafetyConfig
from ..hardware.thermocouple import ThermocoupleReading


@dataclass
class LimitResult:
    safe: bool
    reason: Optional[str] = None


class SafetyLimits:
    def __init__(self, cfg: SafetyConfig) -> None:
        self.cfg = cfg
        self._last_temp: Optional[float] = None
        self._last_ts: Optional[float] = None

    def reset(self) -> None:
        self._last_temp = None
        self._last_ts = None

    def check(self, reading: ThermocoupleReading, now: float) -> LimitResult:
        # 1. Sensor fault (open/short circuit, NaN).
        if reading.fault is not None or not reading.ok:
            self._last_temp = None
            self._last_ts = None
            return LimitResult(False, f"thermocouple fault: {reading.fault}")

        # 2. Stale reading.
        if now - reading.timestamp > self.cfg.sensor_timeout_s:
            return LimitResult(
                False,
                f"stale temperature reading ({now - reading.timestamp:.1f}s old)",
            )

        # 3. Over-temperature.
        if reading.temperature_c >= self.cfg.max_temp_c:
            return LimitResult(
                False,
                f"over-temperature {reading.temperature_c:.1f}C "
                f">= limit {self.cfg.max_temp_c:.1f}C",
            )

        # 4. Implausible rate of rise (likely a sensor glitch).
        if self._last_temp is not None and self._last_ts is not None:
            dt = reading.timestamp - self._last_ts
            if dt > 0:
                rate = (reading.temperature_c - self._last_temp) / dt
                if rate > self.cfg.max_rate_c_per_s:
                    self._last_temp = reading.temperature_c
                    self._last_ts = reading.timestamp
                    return LimitResult(
                        False,
                        f"temperature rising too fast ({rate:.1f}C/s "
                        f"> {self.cfg.max_rate_c_per_s:.1f}C/s)",
                    )

        self._last_temp = reading.temperature_c
        self._last_ts = reading.timestamp
        return LimitResult(True)
