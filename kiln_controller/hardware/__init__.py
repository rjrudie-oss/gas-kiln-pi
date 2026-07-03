"""Hardware abstraction layer.

Each device has a real implementation (backed by the Adafruit CircuitPython /
gpiozero drivers on a Raspberry Pi) and a simulated implementation so the
control and safety logic can be exercised on any machine, in CI, and in tests.

The factory functions pick the implementation based on ``HardwareConfig``.
"""
from __future__ import annotations

from typing import Optional

from ..config import DamperConfig, HardwareConfig
from .actuator import Damper, L298NDamper, SimulatedDamper, TimedDamper
from .thermocouple import (
    MAX31855Thermocouple,
    MAX31856Thermocouple,
    SimulatedThermocouple,
    Thermocouple,
    ThermocoupleReading,
)
from .valve import (
    GasValve,
    MCP4725Valve,
    RelayValve,
    SimulatedValve,
)

__all__ = [
    "Thermocouple",
    "ThermocoupleReading",
    "MAX31856Thermocouple",
    "MAX31855Thermocouple",
    "SimulatedThermocouple",
    "GasValve",
    "RelayValve",
    "MCP4725Valve",
    "SimulatedValve",
    "Damper",
    "TimedDamper",
    "L298NDamper",
    "SimulatedDamper",
    "make_thermocouple",
    "make_valve",
    "make_damper",
]


def make_thermocouple(cfg: HardwareConfig) -> Thermocouple:
    if cfg.simulate:
        return SimulatedThermocouple()
    driver = cfg.thermocouple_driver.lower()
    if driver == "max31856":
        return MAX31856Thermocouple(
            cs_pin=cfg.thermocouple_cs_pin, tc_type=cfg.thermocouple_type
        )
    if driver == "max31855":
        return MAX31855Thermocouple(
            cfg.thermocouple_spi_bus, cfg.thermocouple_spi_device
        )
    raise ValueError(f"unknown thermocouple_driver: {cfg.thermocouple_driver}")


def make_valve(cfg: HardwareConfig) -> GasValve:
    if cfg.simulate:
        return SimulatedValve(full_scale_v=cfg.valve_full_scale_v)
    valve_type = cfg.valve_type.lower()
    if valve_type == "relay":
        return RelayValve(
            gpio=cfg.valve_relay_gpio,
            active_high=cfg.valve_relay_active_high,
            window_s=cfg.valve_pwm_window_s,
        )
    if valve_type == "analog":
        return MCP4725Valve(
            i2c_bus=cfg.dac_i2c_bus,
            address=cfg.dac_i2c_address,
            dac_vref=cfg.dac_vref,
            valve_full_scale_v=cfg.valve_full_scale_v,
            power_gpio=cfg.valve_power_gpio,
        )
    raise ValueError(f"unknown valve_type: {cfg.valve_type}")


def make_damper(cfg: DamperConfig, simulate: bool = False) -> Optional[Damper]:
    """Build the chimney-damper actuator, or ``None`` when it is disabled."""
    if not cfg.enabled:
        return None
    if simulate:
        return SimulatedDamper(
            stroke_time_s=cfg.stroke_time_s,
            invert=cfg.invert,
        )
    driver = cfg.driver.lower()
    if driver == "l298n":
        return L298NDamper(
            in1_gpio=cfg.in1_gpio,
            in2_gpio=cfg.in2_gpio,
            enable_gpio=cfg.enable_gpio,
            stroke_time_s=cfg.stroke_time_s,
            home_on_start=cfg.home_on_start,
            invert=cfg.invert,
        )
    raise ValueError(f"unknown damper driver: {cfg.driver}")
