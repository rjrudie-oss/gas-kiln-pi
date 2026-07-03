# SAFETY

**A gas kiln can leak unburned gas and explode. This software is a convenience
controller, not a safety device. Do not treat it as one.**

## What this software does and does NOT do

**Does:**
- Reads temperature and modulates the gas valve to follow a firing curve.
- Fails the valve **closed** on startup, sensor fault, over-temperature,
  excessive rate-of-rise, stale readings, e-stop, and any software exception.
- Runs an independent watchdog that closes/cuts the valve if the controller
  freezes or dies.

**Does NOT:**
- **Prove flame / detect flame-out.** If the burner flame goes out, this
  software has no reliable way to know, and an open valve keeps releasing gas.
- Replace a certified gas train, manual shutoff, or pressure regulation.

## Strongly recommended before running gas

1. **Certified flame-safeguard.** Install a dedicated, listed flame-supervision
   device (e.g. Honeywell S8610U / S87 series, Fenwal, or a BASO thermocouple
   safety valve) that cuts gas at the hardware level on flame-out, independent
   of the Pi. This is the single most important missing piece.
2. **Manual gas shutoff valve** within reach of the operator.
3. **Combustible-gas / CO detector** in the firing area.
4. **Never fire unattended.**

## Fail-safe wiring (do this regardless)

- Use the **normally-closed** solenoid so no power = no gas.
- Wire the relay so a **de-energized relay leaves the solenoid closed**. Then a
  Pi crash, reboot, brown-out, or pulled wire defaults to gas-off.
- Confirm your relay board's logic (many, incl. SainSmart, are **active-LOW**)
  and set `valve_relay_active_high` accordingly.
- Put an inline **fuse** on the 12 V solenoid feed.
- Give the watchdog a **separate cutoff relay** (`watchdog_relay_gpio`) so it can
  kill gas even if the main relay or its GPIO is stuck.

## Recommended additional hardware safety

- Enable the Pi's **hardware watchdog timer** (`dtparam=watchdog=on`, then
  `RuntimeWatchdogSec` in systemd) so a kernel/OS freeze reboots the board.
- Add a physical **e-stop button** in series with the gas solenoid power, not
  just the software e-stop in the dashboard.
- Mind the thermocouple range: **K-type is only usable to ~1260 °C.** For hotter
  firings use S/R-type wire (the MAX31856 supports them; set `thermocouple_type`).

The software's `safety.max_temp_c` should be set **below** your thermocouple's
limit and below any point of concern for your kiln.
