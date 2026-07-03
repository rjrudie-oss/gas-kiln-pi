"""Gas-fired kiln controller for Raspberry Pi.

SAFETY SCOPE
------------
This software does NOT and MUST NOT manage primary gas ignition or flame-out
safety. An external, hardware-certified flame-safeguard / ignition module
(e.g. Honeywell or BASO) is solely responsible for proving flame and cutting
gas at the hardware level, independent of anything the Raspberry Pi does.

The Raspberry Pi's only jobs are:
  * Read the kiln temperature from a MAX31855 thermocouple amplifier.
  * Modulate a motorized gas valve via a 0-10 V analog signal (MCP4725 DAC)
    to follow a PID temperature curve.

The Pi's analog output only *modulates* an already-proven flame. If the Pi
freezes, crashes, or loses connection, the valve is driven to 0 V (minimum /
closed) by an independent watchdog, and the certified safety module remains
the ultimate authority.
"""

__version__ = "0.1.0"
