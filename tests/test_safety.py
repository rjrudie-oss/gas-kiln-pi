import math
import time

from kiln_controller.config import SafetyConfig
from kiln_controller.hardware.thermocouple import ThermocoupleReading
from kiln_controller.safety.limits import SafetyLimits


def _reading(temp, fault=None, ts=None):
    return ThermocoupleReading(
        temperature_c=temp,
        internal_c=22.0,
        timestamp=ts if ts is not None else time.time(),
        fault=fault,
    )


def test_fault_reading_is_unsafe():
    limits = SafetyLimits(SafetyConfig())
    res = limits.check(_reading(math.nan, fault="open circuit"), time.time())
    assert not res.safe


def test_over_temperature_is_unsafe():
    cfg = SafetyConfig(max_temp_c=1000.0)
    limits = SafetyLimits(cfg)
    assert not limits.check(_reading(1000.0), time.time()).safe
    assert limits.check(_reading(999.0), time.time()).safe


def test_stale_reading_is_unsafe():
    cfg = SafetyConfig(sensor_timeout_s=2.0)
    limits = SafetyLimits(cfg)
    now = time.time()
    assert not limits.check(_reading(500.0, ts=now - 5.0), now).safe


def test_excess_rate_of_rise_is_unsafe():
    cfg = SafetyConfig(max_rate_c_per_s=5.0)
    limits = SafetyLimits(cfg)
    t0 = 1000.0
    assert limits.check(_reading(100.0, ts=t0), t0).safe
    # +100 C in 1 s == 100 C/s, way over limit.
    assert not limits.check(_reading(200.0, ts=t0 + 1.0), t0 + 1.0).safe
