"""Safety subsystem: heartbeat, limit checks, and the fail-safe watchdog."""
from .heartbeat import Heartbeat, read_heartbeat, write_heartbeat
from .limits import LimitResult, SafetyLimits

__all__ = [
    "Heartbeat",
    "read_heartbeat",
    "write_heartbeat",
    "SafetyLimits",
    "LimitResult",
]
