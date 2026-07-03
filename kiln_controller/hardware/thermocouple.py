"""MAX31856 (and legacy MAX31855) thermocouple interface.

The MAX31856 is a universal thermocouple amplifier (supports K/J/N/R/S/T/E/B)
with programmable fault detection. It reports the hot-junction (kiln)
temperature plus fault bits (open circuit, over/under range, cold-junction
fault). Any fault is surfaced to the caller so the control loop can fail safe
rather than acting on a bogus temperature.

``MAX31855Thermocouple`` is kept for boards that use the older, K-type-only amp.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class ThermocoupleReading:
    temperature_c: float
    internal_c: float
    timestamp: float
    fault: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.fault is None and self.temperature_c == self.temperature_c  # not NaN


class Thermocouple(Protocol):
    def read(self) -> ThermocoupleReading: ...


_THERMOCOUPLE_TYPES = {
    "B", "E", "J", "K", "N", "R", "S", "T",
}


class MAX31856Thermocouple:
    """Real MAX31856 backed by Adafruit CircuitPython (lazy-imported).

    ``cs_pin`` is a ``board`` pin name such as ``"D5"`` (BCM GPIO5). On a Pi 5
    the Adafruit Blinka layer talks to the SPI hardware via lgpio.
    """

    def __init__(self, cs_pin: str = "D5", tc_type: str = "K") -> None:
        import board  # type: ignore
        import busio  # type: ignore
        import digitalio  # type: ignore
        import adafruit_max31856  # type: ignore

        tc_type = tc_type.upper()
        if tc_type not in _THERMOCOUPLE_TYPES:
            raise ValueError(f"unsupported thermocouple type: {tc_type}")

        spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        cs = digitalio.DigitalInOut(getattr(board, cs_pin))
        thermocouple_type = getattr(
            adafruit_max31856.ThermocoupleType, f"{tc_type}"
        )
        self._sensor = adafruit_max31856.MAX31856(
            spi, cs, thermocouple_type=thermocouple_type
        )

    def read(self) -> ThermocoupleReading:
        now = time.time()
        try:
            faults = self._sensor.fault
            active = [name for name, tripped in faults.items() if tripped]
            if active:
                return ThermocoupleReading(
                    temperature_c=math.nan,
                    internal_c=math.nan,
                    timestamp=now,
                    fault=", ".join(active),
                )
            temp = float(self._sensor.temperature)
            internal = float(self._sensor.reference_temperature)
        except Exception as exc:  # surface any driver error as a fault
            return ThermocoupleReading(
                math.nan, math.nan, now, fault=str(exc) or "thermocouple error"
            )
        return ThermocoupleReading(
            temperature_c=temp, internal_c=internal, timestamp=now, fault=None
        )


class MAX31855Thermocouple:
    """Real MAX31855 backed by Adafruit CircuitPython (lazy-imported)."""

    def __init__(self, spi_bus: int = 0, spi_device: int = 0) -> None:
        # Imported lazily so the module loads on machines without the HW libs.
        import board  # type: ignore
        import busio  # type: ignore
        import digitalio  # type: ignore
        import adafruit_max31855  # type: ignore

        spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        cs = digitalio.DigitalInOut(getattr(board, f"D{spi_device}", board.D5))
        self._sensor = adafruit_max31855.MAX31855(spi, cs)

    def read(self) -> ThermocoupleReading:
        now = time.time()
        try:
            temp = float(self._sensor.temperature)
            internal = float(self._sensor.reference_temperature)
        except RuntimeError as exc:
            # The Adafruit driver raises RuntimeError on the fault bits.
            return ThermocoupleReading(
                temperature_c=math.nan,
                internal_c=math.nan,
                timestamp=now,
                fault=str(exc) or "thermocouple fault",
            )
        return ThermocoupleReading(
            temperature_c=temp, internal_c=internal, timestamp=now, fault=None
        )


class SimulatedThermocouple:
    """A simple first-order kiln thermal model for off-hardware testing.

    Temperature rises toward a heat-input-dependent asymptote and always leaks
    toward ambient, so it behaves plausibly for a PID loop and for the web
    dashboard demo.
    """

    def __init__(
        self,
        ambient_c: float = 22.0,
        tau_s: float = 600.0,
        clock=time.time,
    ) -> None:
        self.ambient_c = ambient_c
        self.tau_s = tau_s
        self._clock = clock
        self._temp = ambient_c
        self._last = clock()
        self._valve_fraction = 0.0
        self._fault: Optional[str] = None
        # Full valve => this many degrees above ambient at steady state. With
        # the default tau this gives a plausible peak rise of a few deg C/s.
        self._max_rise_c = 1350.0

    def set_valve_fraction(self, fraction: float) -> None:
        self._valve_fraction = max(0.0, min(1.0, fraction))

    def inject_fault(self, fault: Optional[str]) -> None:
        self._fault = fault

    def read(self) -> ThermocoupleReading:
        now = self._clock()
        dt = max(1e-3, now - self._last)
        self._last = now
        target = self.ambient_c + self._valve_fraction * self._max_rise_c
        # Exponential approach toward target.
        alpha = 1.0 - math.exp(-dt / self.tau_s)
        self._temp += (target - self._temp) * alpha
        if self._fault is not None:
            return ThermocoupleReading(math.nan, math.nan, now, fault=self._fault)
        return ThermocoupleReading(
            temperature_c=round(self._temp, 3),
            internal_c=self.ambient_c,
            timestamp=now,
            fault=None,
        )
