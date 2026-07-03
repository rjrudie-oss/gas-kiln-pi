# Wiring (Raspberry Pi 5)

Pins are **BCM** numbers (what the code/config use). Double-check against a
Pi 5 pinout diagram and the labels on your Freenove breakout HAT.

> ⚠️ Read [`../SAFETY.md`](../SAFETY.md) first. Wire everything so **loss of
> power = gas off**.

## MAX31856 thermocouple amplifier (SPI)

| MAX31856 | Pi 5 (BCM) | Physical pin |
|----------|------------|--------------|
| VIN      | 3V3        | 1            |
| GND      | GND        | 6            |
| SCK      | SCLK/GPIO11| 23           |
| SDO (MISO)| MISO/GPIO9| 21           |
| SDI (MOSI)| MOSI/GPIO10| 19          |
| CS       | GPIO5      | 29           |

- Set `hardware.thermocouple_cs_pin: D5` (GPIO5). Any free GPIO works; update
  the config if you use another.
- Connect the K-type thermocouple to the board's **T+ / T−** screw terminals
  (mind polarity; if the reading drops when heating, swap them).
- Enable SPI: `sudo raspi-config` → Interface Options → SPI → enable.

## Relay → 12 V normally-closed gas solenoid

Relay board (e.g. SainSmart 4-ch):

| Relay | Connect to |
|-------|------------|
| VCC   | Pi 5V (pin 2) — or a separate 5V; keep grounds common |
| GND   | Pi GND |
| IN1   | GPIO17 (BCM) → `valve_relay_gpio: 17` |
| IN2   | GPIO27 (optional watchdog cutoff) → `watchdog_relay_gpio: 27` |

Solenoid power path (12 V, use the ALITOVE 12 V supply, **fused**):

```
12V+  --[fuse]--> Relay COM
Relay NO --------> Solenoid +
Solenoid - ------> 12V-  (PSU ground)
```

- Use the relay's **NO (normally-open)** contact so the solenoid is powered
  **only** while the relay is energized. Combined with the **normally-closed**
  solenoid, gas flows only when the Pi actively commands it.
- Many relay boards energize on a **LOW** input. If yours does, set
  `valve_relay_active_high: false`. Test with the solenoid **disconnected from
  gas** first and confirm the click/logic matches "closed at rest".

## Grounding & power

- Common all grounds: Pi GND, relay GND, 12 V PSU −.
- Do **not** power the 12 V solenoid from the Pi. Use the 12 V supply.
- Keep thermocouple wiring away from the 12 V/mains runs to reduce noise; use
  the ceramic protection sheath in the kiln.

## Optional / future

- **Modulating valve upgrade:** an MCP4725 DAC (+0-10 V gain stage) driving a
  proportional valve — set `valve_type: analog`. Or drive the 4" linear
  actuator via the L298N to move a mechanical valve (needs position feedback).
- **Bosch O2 sensor:** could give a rough reduction/oxidation reading via the
  ADS1115 ADC — not wired into control here.
