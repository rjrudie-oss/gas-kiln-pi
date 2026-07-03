"""Shared runtime state, published atomically for the web dashboard.

The controller writes a JSON snapshot; the web process reads it. Using a file
(with an atomic rename) keeps the controller and the dashboard decoupled: if
the dashboard crashes it can never stall or crash the control loop.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class KilnState:
    timestamp: float = field(default_factory=time.time)
    temperature_c: Optional[float] = None
    setpoint_c: Optional[float] = None
    valve_percent: float = 0.0
    valve_voltage: Optional[float] = None
    pid_output: float = 0.0
    damper_enabled: bool = False
    damper_position: Optional[float] = None
    damper_target: Optional[float] = None
    running: bool = False
    fault: Optional[str] = None
    safe_state: bool = True  # True == valve forced closed by a safety condition
    profile_elapsed_s: float = 0.0
    profile_finished: bool = False
    message: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self))


def write_state(path: str, state: KilnState) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".state-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(state.to_json())
        os.replace(tmp, path)  # atomic on POSIX
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def read_state(path: str) -> Optional[KilnState]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return KilnState(**data)
