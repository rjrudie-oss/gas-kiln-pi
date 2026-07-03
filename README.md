# gas-kiln-pi

A Raspberry Pi 5 PID controller, dashboard, and fail-safe watchdog for a
gas-fired kiln.

The Raspberry Pi:

- reads kiln temperature from a **MAX31856** thermocouple amplifier (K-type),
- follows a **firing profile** (ramp/hold segments) with a **PID loop**,
- modulates gas by **time-proportional (slow-PWM) on/off control** of a
  **12 V normally-closed solenoid** through a relay channel,
- optionally positions a **chimney damper** with a 12 V linear actuator through
  an L298N H-bridge (position estimated by timing the stroke; disabled by
  default, enable with `damper.enabled: true`),
- serves a **lightweight web dashboard** for monitoring, emergency stop, and
  (when enabled) a damper-position slider.

The valve command defaults to **closed** on startup, on any sensor fault,
on over-temperature, and on any unhandled exception.

> ⚠️ **Read [`SAFETY.md`](SAFETY.md) before connecting gas.** This software
> modulates gas; it does **not** provide flame supervision. Flame-out / ignition
> safety must be handled by dedicated, certified hardware.

## Architecture

```
                +------------------+      MAX31856 (SPI)      +-----------+
                |  Raspberry Pi 5  |<-------------------------| K-type TC |
                |                  |                          +-----------+
   web UI  <--->|  dashboard (Flask)                                      
                |        ^ reads state.json                               
                |        |                                                
                |  controller (PID) --GPIO--> relay --> 12V NC solenoid --> gas
                |        |  writes heartbeat                                
                |        v                                                 
                |  watchdog (separate process) --GPIO--> cutoff relay      
                +------------------+                                       
```

- **`kiln_controller/controller.py`** — the PID control loop.
- **`kiln_controller/control/pid.py`** — PID (anti-windup, derivative-on-measurement).
- **`kiln_controller/control/profile.py`** — ramp/hold firing schedule.
- **`kiln_controller/hardware/`** — MAX31856/MAX31855 and relay/MCP4725 drivers,
  each with a simulation backend so everything runs off-Pi.
- **`kiln_controller/safety/`** — in-loop limit checks, heartbeat, watchdog.
- **`kiln_controller/web/`** — Flask dashboard (monitor + e-stop only).

Processes communicate through small files (atomic writes), so a dashboard or
watchdog problem can never stall or crash the control loop.

## Install

### Off-Pi (development / simulation)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pip install -e .
pytest -q          # run tests
ruff check .       # lint
```

Run the whole thing in simulation (no hardware needed). `config.yaml` ships with
`hardware.simulate: true`:

```bash
python scripts/run_controller.py -c config.yaml --state-path ./run/state.json &
python scripts/run_dashboard.py  -c config.yaml --state-path ./run/state.json
# open http://localhost:8080
```

### On the Raspberry Pi 5

1. Enable SPI (thermocouple) and I2C (optional): `sudo raspi-config` →
   *Interface Options*.
2. Install deps:
   ```bash
   pip install -r requirements-pi.txt
   pip install -e .
   ```
3. Set `hardware.simulate: false` in `config.yaml` and set the pins to match
   your wiring (see [`docs/WIRING.md`](docs/WIRING.md)).
4. Install services (adjust paths / user in the unit files first):
   ```bash
   sudo cp systemd/*.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now kiln-controller kiln-dashboard
   # optional watchdog (needs a dedicated cutoff relay pin, see config):
   sudo systemctl enable --now kiln-watchdog
   ```

## Configuration

All settings live in `config.yaml` (env var `KILN_CONFIG` overrides the path).
Key sections: `hardware` (driver + pins), `pid` (gains), `safety` (limits,
heartbeat), `control` (loop rate + firing `profile`), `web`.

The firing `profile` is a list of `[target_C, ramp_C_per_hour, hold_minutes]`
steps. An empty list keeps the valve closed.

## PID tuning

Start with the shipped gains and tune on a real (empty) kiln:

1. Set `ki: 0` and `kd: 0`, raise `kp` until the temperature oscillates, then
   back off to ~half.
2. Add `kd` to damp overshoot.
3. Add a small `ki` to remove steady-state offset. Keep `integral_limit` modest
   to avoid windup during long ramps.

## Tests

`pytest` covers the PID math, the firing profile, the safety limit checks, and
the control loop (fault → valve closed, e-stop → valve closed, heats toward
setpoint) using a deterministic simulated kiln.
