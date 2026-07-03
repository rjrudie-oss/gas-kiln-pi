"""Heartbeat file used by the independent watchdog.

The controller updates a small file with a monotonic-ish wall-clock timestamp
on every loop iteration. The watchdog (a *separate process*) reads it. If the
file is missing or older than the configured timeout, the watchdog assumes the
controller has frozen, crashed, or lost the plot and drives the valve closed.

A file-based heartbeat is deliberately simple and robust: it survives the
controller being killed (the file just stops updating) and needs no IPC that
could itself hang.
"""
from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from typing import Optional


def write_heartbeat(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".hb-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(str(time.time()))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def read_heartbeat(path: str) -> Optional[float]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return float(fh.read().strip())
    except (FileNotFoundError, ValueError):
        return None


@dataclass
class Heartbeat:
    path: str

    def beat(self) -> None:
        write_heartbeat(self.path)

    def age(self) -> Optional[float]:
        ts = read_heartbeat(self.path)
        if ts is None:
            return None
        return time.time() - ts

    def is_alive(self, timeout_s: float) -> bool:
        age = self.age()
        return age is not None and age <= timeout_s
