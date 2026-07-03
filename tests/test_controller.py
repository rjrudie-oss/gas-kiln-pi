from kiln_controller.config import Config
from kiln_controller.controller import KilnController
from kiln_controller.hardware.thermocouple import SimulatedThermocouple
from kiln_controller.hardware.valve import SimulatedValve


class FakeClock:
    """Deterministic, advanceable clock shared by the sensor and the loop."""

    def __init__(self, start=1000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def _controller(tmp_path, **profile):
    cfg = Config()
    cfg.hardware.simulate = True
    cfg.control.profile = profile.get("profile", [(200.0, 0.0, 5.0)])
    cfg.safety.estop_path = str(tmp_path / "estop")
    cfg.safety.heartbeat_path = str(tmp_path / "hb")
    clock = FakeClock()
    tc = SimulatedThermocouple(ambient_c=22.0, tau_s=300.0, clock=clock)
    valve = SimulatedValve()
    ctrl = KilnController(cfg, thermocouple=tc, valve=valve,
                          state_path=str(tmp_path / "state.json"))
    return ctrl, tc, valve, clock


def test_valve_opens_when_below_setpoint(tmp_path):
    ctrl, _tc, _valve, clock = _controller(tmp_path)
    ctrl.start()
    state = ctrl.tick(now=clock())
    assert state.valve_percent > 0
    assert not state.safe_state


def test_thermocouple_fault_forces_closed(tmp_path):
    ctrl, tc, valve, clock = _controller(tmp_path)
    ctrl.start()
    ctrl.tick(now=clock())
    clock.advance(1.0)
    tc.inject_fault("open circuit")
    state = ctrl.tick(now=clock())
    assert state.safe_state
    assert state.valve_percent == 0.0
    assert valve.commanded_percent == 0.0


def test_estop_forces_closed(tmp_path):
    ctrl, _tc, valve, clock = _controller(tmp_path)
    ctrl.start()
    ctrl.tick(now=clock())
    clock.advance(1.0)
    with open(ctrl.cfg.safety.estop_path, "w") as fh:
        fh.write("engaged")
    state = ctrl.tick(now=clock())
    assert state.safe_state
    assert valve.commanded_percent == 0.0


def test_control_loop_heats_toward_setpoint(tmp_path):
    ctrl, _tc, _valve, clock = _controller(tmp_path, profile=[(300.0, 0.0, 60.0)])
    ctrl.start()
    last = None
    for _ in range(400):
        last = ctrl.tick(now=clock())
        clock.advance(1.0)
    assert last.temperature_c is not None
    assert last.temperature_c > 150.0  # made real progress toward 300
