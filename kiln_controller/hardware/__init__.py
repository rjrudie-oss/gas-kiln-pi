"""Hardware abstraction layer.

Each device has a real implementation (backed by the Adafruit CircuitPython /
gpiozero drivers on a Raspberry Pi) and a simulated implementation so the
control and safety logic can be exercised on any machine, in CI, and in tests.

The factory functions pick the implementation based on ``HardwareConfig``.
"""
from __future__ import annotations

from ..config import HardwareConfig
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
    "make_thermocouple",
    "make_valve",
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
