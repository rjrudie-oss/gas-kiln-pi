"""Firing profile: a sequence of ramp-and-hold segments.

Each step ramps from wherever the kiln currently is toward ``target_c`` at
``ramp_c_per_hour``, then holds at ``target_c`` for ``hold_minutes``. The
profile computes the *current* setpoint as a function of elapsed time, which is
what the PID loop tracks. A ramp rate of 0 or less means "go as fast as the
kiln can" (setpoint jumps straight to target).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ProfileStep:
    target_c: float
    ramp_c_per_hour: float
    hold_minutes: float


class FiringProfile:
    def __init__(self, steps: Sequence[ProfileStep], start_temp_c: float = 22.0) -> None:
        self.steps: List[ProfileStep] = list(steps)
        self.start_temp_c = start_temp_c
        self._elapsed = 0.0
        self._finished = not self.steps

    @classmethod
    def from_tuples(
        cls, tuples: Sequence[Tuple[float, float, float]], start_temp_c: float = 22.0
    ) -> "FiringProfile":
        return cls([ProfileStep(*t) for t in tuples], start_temp_c=start_temp_c)

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def elapsed_s(self) -> float:
        return self._elapsed

    def reset(self, start_temp_c: Optional[float] = None) -> None:
        self._elapsed = 0.0
        self._finished = not self.steps
        if start_temp_c is not None:
            self.start_temp_c = start_temp_c

    def advance(self, dt: float) -> None:
        self._elapsed += max(0.0, dt)

    def setpoint(self) -> float:
        """Return the scheduled setpoint at the current elapsed time."""
        if not self.steps:
            return self.start_temp_c

        t = self._elapsed
        seg_start_temp = self.start_temp_c
        for step in self.steps:
            ramp_per_s = step.ramp_c_per_hour / 3600.0
            delta = step.target_c - seg_start_temp
            if ramp_per_s > 0 and delta != 0:
                ramp_duration = abs(delta) / ramp_per_s
            else:
                ramp_duration = 0.0
            hold_duration = max(0.0, step.hold_minutes) * 60.0

            if t <= ramp_duration:
                frac = 0.0 if ramp_duration == 0 else t / ramp_duration
                return seg_start_temp + delta * frac
            t -= ramp_duration
            if t <= hold_duration:
                return step.target_c
            t -= hold_duration
            seg_start_temp = step.target_c

        self._finished = True
        return self.steps[-1].target_c

    def total_duration_s(self) -> float:
        total = 0.0
        seg_start_temp = self.start_temp_c
        for step in self.steps:
            ramp_per_s = step.ramp_c_per_hour / 3600.0
            delta = step.target_c - seg_start_temp
            if ramp_per_s > 0 and delta != 0:
                total += abs(delta) / ramp_per_s
            total += max(0.0, step.hold_minutes) * 60.0
            seg_start_temp = step.target_c
        return total
