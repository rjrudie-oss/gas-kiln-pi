"""Configuration loading and validation.

Configuration is read from a YAML file (default ``config.yaml``). Every value
has a conservative, fail-safe default so that a missing or partial config never
produces an unsafe setpoint.
"""
from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field
from typing import List, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a declared dependency
    yaml = None


@dataclass
class PIDConfig:
    kp: float = 2.0
    ki: float = 0.01
    kd: float = 15.0
    # Output is a valve command in percent (0-100). 0 % == fully closed.
    output_min: float = 0.0
    output_max: float = 100.0
    # Anti-windup clamp on the integral term (in output units).
    integral_limit: float = 100.0


@dataclass
class SafetyConfig:
    # Absolute maximum kiln temperature. Above this the valve is forced closed.
    # Default is conservative for a K-type thermocouple (usable to ~1260 C).
    max_temp_c: float = 1250.0
    # Maximum plausible rate of rise (deg C / second). Faster than this is
    # treated as a sensor fault and forces the valve closed.
    max_rate_c_per_s: float = 10.0
    # If no fresh temperature reading arrives within this many seconds, the
    # reading is considered stale and the valve is forced closed.
    sensor_timeout_s: float = 5.0
    # The controller must refresh its heartbeat at least this often. The
    # watchdog closes the valve if the heartbeat goes older than
    # ``heartbeat_timeout_s``.
    heartbeat_interval_s: float = 1.0
    heartbeat_timeout_s: float = 3.0
    heartbeat_path: str = "/run/kiln/heartbeat"
    # Presence of this file forces the valve closed (software emergency stop).
    estop_path: str = "/run/kiln/estop"


@dataclass
class HardwareConfig:
    # Set to True to run without real hardware (SPI/I2C libs not required).
    simulate: bool = False

    # --- Thermocouple amplifier -----------------------------------------
    # "max31856" (universal amp, the board you have) or "max31855" (legacy).
    thermocouple_driver: str = "max31856"
    # MAX31856 chip-select pin, as a board pin name (BCM: D5 == GPIO5).
    thermocouple_cs_pin: str = "D5"
    thermocouple_type: str = "K"  # K/J/N/R/S/T/E/B
    # Legacy MAX31855 SPI selection (only used when driver == "max31855").
    thermocouple_spi_bus: int = 0
    thermocouple_spi_device: int = 0

    # --- Valve actuator --------------------------------------------------
    # "relay" (time-proportional on/off solenoid, the parts you have) or
    # "analog" (0-10 V modulating valve via MCP4725 DAC, future upgrade).
    valve_type: str = "relay"

    # Relay / solenoid control:
    valve_relay_gpio: int = 17  # BCM pin driving the relay channel
    # Many relay boards (incl. SainSmart) energize on a LOW signal. Set False
    # for active-low boards. Contacts are still wired so de-energized == gas off.
    valve_relay_active_high: bool = True
    valve_pwm_window_s: float = 10.0

    # The independent watchdog drives a SEPARATE relay channel that cuts power
    # to the solenoid entirely, so it never fights the controller for the same
    # GPIO line. -1 == fall back to the main relay pin (only safe if you do NOT
    # run the controller and watchdog at the same time).
    watchdog_relay_gpio: int = -1

    # Analog (MCP4725) valve, kept for a future modulating-valve upgrade:
    dac_i2c_address: int = 0x60
    dac_i2c_bus: int = 1
    dac_vref: float = 5.0
    valve_full_scale_v: float = 10.0
    valve_power_gpio: int = -1


@dataclass
class DamperConfig:
    # Chimney-damper linear actuator via an L298N H-bridge. Disabled by default;
    # the core kiln controller runs fine without it.
    enabled: bool = False
    # "l298n" (real driver) is the only hardware option; simulation is picked
    # automatically when hardware.simulate is true.
    driver: str = "l298n"
    # BCM pins wired to the L298N IN1 / IN2 inputs for the damper motor.
    in1_gpio: int = 23
    in2_gpio: int = 24
    # ENA (enable) pin. -1 == leave the board's ENA jumper on (always enabled).
    enable_gpio: int = -1
    # Seconds for one full stroke (retracted <-> extended). Time it on the bench.
    stroke_time_s: float = 20.0
    # Drive to the retracted limit once on startup to establish the 0 % point.
    home_on_start: bool = True
    # Flip if the actuator moves the opposite way from what you expect.
    invert: bool = False
    # Position (0-100 %) held on startup and whenever no command has been issued.
    default_percent: float = 0.0
    # File the dashboard writes the requested damper position (0-100) to.
    command_path: str = "/run/kiln/damper"


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    poll_interval_s: float = 1.0


@dataclass
class ControlConfig:
    loop_interval_s: float = 1.0
    # Firing schedule: list of (target_temp_c, ramp_c_per_hour, hold_minutes).
    # An empty schedule means "hold at ambient / valve closed".
    profile: List[Tuple[float, float, float]] = field(default_factory=list)


@dataclass
class Config:
    pid: PIDConfig = field(default_factory=PIDConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    damper: DamperConfig = field(default_factory=DamperConfig)
    web: WebConfig = field(default_factory=WebConfig)
    control: ControlConfig = field(default_factory=ControlConfig)

    @classmethod
    def load(cls, path: str | None = None) -> "Config":
        path = path or os.environ.get("KILN_CONFIG", "config.yaml")
        data: dict = {}
        if path and os.path.exists(path):
            if yaml is None:
                raise RuntimeError("PyYAML is required to read a config file")
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        return cls(
            pid=PIDConfig(**data.get("pid", {})),
            safety=SafetyConfig(**data.get("safety", {})),
            hardware=HardwareConfig(**_parse_hw(data.get("hardware", {}))),
            damper=DamperConfig(**data.get("damper", {})),
            web=WebConfig(**data.get("web", {})),
            control=ControlConfig(**_parse_control(data.get("control", {}))),
        )

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def _parse_hw(d: dict) -> dict:
    d = dict(d)
    # Allow hex strings like "0x60" for the I2C address.
    addr = d.get("dac_i2c_address")
    if isinstance(addr, str):
        d["dac_i2c_address"] = int(addr, 0)
    return d


def _parse_control(d: dict) -> dict:
    d = dict(d)
    if "profile" in d and d["profile"]:
        d["profile"] = [tuple(step) for step in d["profile"]]
    return d
