"""Chimney-damper linear-actuator drivers.

The damper is positioned by a 12 V linear actuator driven through an L298N
H-bridge. The actuator has built-in end-of-travel limit switches but **no
position feedback**, so position is estimated by *timing the stroke*:

  * ``stroke_time_s`` is how long a full travel (retracted <-> extended) takes.
  * On startup the actuator is "homed" by driving it to the retracted limit for
    a little longer than one full stroke; the internal limit switch stops the
    mechanism, and we then call that position 0 %.
  * Thereafter each :meth:`update` drives the motor toward the target and
    advances the estimated position by ``dt / stroke_time_s``.

:meth:`update` is non-blocking: the motor is simply left running in the chosen
direction between calls, so the control loop is never stalled waiting for the
damper to move.

Convention: 0 % == fully retracted, 100 % == fully extended. Which of those is
"damper open" depends on your linkage; set ``invert: true`` in the config if the
actuator moves the wrong way.
"""
from __future__ import annotations

from typing import Protocol


def _clamp01(value: float) -> float:
    if value != value:  # NaN
        return 0.0
    return max(0.0, min(1.0, float(value)))


class Damper(Protocol):
    def set_target_percent(self, percent: float) -> None: ...
    def update(self, dt: float) -> None: ...
    def stop(self) -> None: ...
    @property
    def position_percent(self) -> float: ...
    @property
    def target_percent(self) -> float: ...


class TimedDamper:
    """Position-by-timing core, independent of any hardware.

    Subclasses implement :meth:`_drive` to move a physical motor. ``direction``
    is +1 (extend), -1 (retract) or 0 (stop), already adjusted for ``invert``.
    """

    def __init__(
        self,
        stroke_time_s: float = 20.0,
        home_on_start: bool = True,
        invert: bool = False,
        deadband_frac: float = 0.03,
        home_margin: float = 0.15,
    ) -> None:
        self._stroke = max(1.0, float(stroke_time_s))
        self._invert = bool(invert)
        self._deadband = max(0.0, float(deadband_frac))
        self._home_margin = max(0.0, float(home_margin))
        self._target = 0.0
        self._position = 0.0
        self._homed = not home_on_start
        self._home_elapsed = 0.0
        self._direction = 0

    # -- hardware hook -----------------------------------------------------
    def _drive(self, direction: int) -> None:  # pragma: no cover - overridden
        """Drive the motor. ``direction`` in {-1, 0, +1}."""

    def _apply_direction(self, direction: int) -> None:
        self._direction = direction
        physical = -direction if self._invert else direction
        self._drive(physical)

    # -- public API --------------------------------------------------------
    def set_target_percent(self, percent: float) -> None:
        self._target = _clamp01(float(percent) / 100.0)

    def update(self, dt: float) -> None:
        dt = max(0.0, float(dt))

        # Homing: drive to the retracted limit to establish the 0 % reference.
        if not self._homed:
            self._apply_direction(-1)
            self._home_elapsed += dt
            if self._home_elapsed >= self._stroke * (1.0 + self._home_margin):
                self._apply_direction(0)
                self._position = 0.0
                self._homed = True
            return

        error = self._target - self._position
        if abs(error) <= self._deadband:
            self._apply_direction(0)
            self._position = self._target
            return

        step = dt / self._stroke
        if error > 0:
            self._apply_direction(1)
            self._position = min(self._target, self._position + step)
        else:
            self._apply_direction(-1)
            self._position = max(self._target, self._position - step)

    def stop(self) -> None:
        self._apply_direction(0)

    # -- introspection -----------------------------------------------------
    @property
    def position_percent(self) -> float:
        return self._position * 100.0

    @property
    def target_percent(self) -> float:
        return self._target * 100.0

    @property
    def homed(self) -> bool:
        return self._homed

    @property
    def direction(self) -> int:
        return self._direction


class L298NDamper(TimedDamper):
    """Linear actuator driven through an L298N H-bridge (lazy gpiozero import).

    ``in1_gpio`` / ``in2_gpio`` are the BCM pins wired to the L298N ``IN1`` /
    ``IN2`` inputs for this motor channel. ``enable_gpio`` is the ``ENA`` pin; set
    it to ``-1`` if you leave the board's ENA jumper on (motor always enabled).
    """

    def __init__(
        self,
        in1_gpio: int,
        in2_gpio: int,
        enable_gpio: int = -1,
        stroke_time_s: float = 20.0,
        home_on_start: bool = True,
        invert: bool = False,
    ) -> None:
        super().__init__(
            stroke_time_s=stroke_time_s,
            home_on_start=home_on_start,
            invert=invert,
        )
        import gpiozero  # type: ignore

        self._in1 = gpiozero.OutputDevice(in1_gpio, active_high=True, initial_value=False)
        self._in2 = gpiozero.OutputDevice(in2_gpio, active_high=True, initial_value=False)
        self._enable = None
        if enable_gpio is not None and enable_gpio >= 0:
            self._enable = gpiozero.OutputDevice(
                enable_gpio, active_high=True, initial_value=True
            )

    def _drive(self, direction: int) -> None:
        if self._enable is not None:
            self._enable.on()
        if direction > 0:
            self._in1.on()
            self._in2.off()
        elif direction < 0:
            self._in1.off()
            self._in2.on()
        else:  # coast/stop
            self._in1.off()
            self._in2.off()


class SimulatedDamper(TimedDamper):
    """In-memory damper for simulation, CI and tests (starts homed at 0 %)."""

    def __init__(self, stroke_time_s: float = 20.0, **kwargs) -> None:
        kwargs.setdefault("home_on_start", False)
        super().__init__(stroke_time_s=stroke_time_s, **kwargs)

    def _drive(self, direction: int) -> None:  # no hardware
        return None
