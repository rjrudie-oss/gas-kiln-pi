"""A discrete PID controller with anti-windup and derivative-on-measurement.

Derivative-on-measurement avoids a derivative "kick" when the setpoint changes,
which matters for a slowly-ramped kiln profile. The integral term is clamped
(anti-windup) so a long approach to setpoint cannot accumulate a huge burst of
gas that overshoots.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PID:
    kp: float
    ki: float
    kd: float
    output_min: float = 0.0
    output_max: float = 100.0
    integral_limit: float = 100.0

    def __post_init__(self) -> None:
        self._integral = 0.0
        self._last_measurement: float | None = None
        self._last_output = 0.0

    def reset(self) -> None:
        self._integral = 0.0
        self._last_measurement = None
        self._last_output = 0.0

    @property
    def last_output(self) -> float:
        return self._last_output

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def update(self, setpoint: float, measurement: float, dt: float) -> float:
        if dt <= 0.0:
            return self._last_output

        error = setpoint - measurement

        # Proportional.
        p = self.kp * error

        # Integral with clamping (anti-windup).
        self._integral += error * dt
        self._integral = self._clamp(
            self._integral, -self.integral_limit, self.integral_limit
        )
        i = self.ki * self._integral

        # Derivative on measurement (negative sign) to avoid setpoint kick.
        if self._last_measurement is None:
            d = 0.0
        else:
            d = -self.kd * (measurement - self._last_measurement) / dt
        self._last_measurement = measurement

        output = p + i + d
        clamped = self._clamp(output, self.output_min, self.output_max)

        # Conditional anti-windup: if we saturated, back the integral out so it
        # does not keep growing while the actuator is pinned.
        if output != clamped and self.ki != 0.0:
            self._integral -= (output - clamped) / self.ki
            self._integral = self._clamp(
                self._integral, -self.integral_limit, self.integral_limit
            )

        self._last_output = clamped
        return clamped
