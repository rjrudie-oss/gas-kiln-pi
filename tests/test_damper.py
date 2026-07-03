from kiln_controller.config import Config
from kiln_controller.controller import KilnController
from kiln_controller.hardware.actuator import SimulatedDamper, TimedDamper


class RecordingDamper(TimedDamper):
    """TimedDamper that records the physical drive directions it emits."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.calls = []

    def _drive(self, direction):
        self.calls.append(direction)


def test_moves_toward_target_and_stops():
    d = SimulatedDamper(stroke_time_s=10.0)
    d.set_target_percent(50.0)
    for _ in range(60):  # 60 s, plenty for a 10 s stroke
        d.update(1.0)
    assert abs(d.position_percent - 50.0) < 1.0
    # Once at target it stops (coasts), not driving anymore.
    assert d.direction == 0


def test_position_tracks_stroke_time():
    d = SimulatedDamper(stroke_time_s=10.0)
    d.set_target_percent(100.0)
    d.update(3.0)  # 3 s of a 10 s stroke -> ~30 %
    assert abs(d.position_percent - 30.0) < 1e-6
    assert d.direction == 1


def test_does_not_overshoot_target():
    d = SimulatedDamper(stroke_time_s=10.0)
    d.set_target_percent(20.0)
    d.update(5.0)  # would be 50 % without clamping
    assert abs(d.position_percent - 20.0) < 1e-6


def test_retracts_when_target_below_position():
    d = SimulatedDamper(stroke_time_s=10.0)
    d.set_target_percent(80.0)
    for _ in range(20):
        d.update(1.0)
    d.set_target_percent(30.0)
    d.update(2.0)  # retract 20 %
    assert abs(d.position_percent - 60.0) < 1e-6
    assert d.direction == -1


def test_homing_drives_retract_then_zeroes():
    d = RecordingDamper(stroke_time_s=10.0, home_on_start=True)
    d.set_target_percent(100.0)
    # Before homing completes it keeps driving retract (-1) regardless of target.
    d.update(5.0)
    assert not d.homed
    assert d.calls[-1] == -1
    # Finish homing (needs stroke * 1.15 = 11.5 s total).
    d.update(7.0)
    assert d.homed
    assert d.position_percent == 0.0


def test_invert_flips_physical_direction():
    normal = RecordingDamper(stroke_time_s=10.0, home_on_start=False)
    inverted = RecordingDamper(stroke_time_s=10.0, home_on_start=False, invert=True)
    normal.set_target_percent(100.0)
    inverted.set_target_percent(100.0)
    normal.update(1.0)
    inverted.update(1.0)
    assert normal.calls[-1] == 1
    assert inverted.calls[-1] == -1  # same logical extend, opposite physical


def test_controller_positions_damper_from_command_file(tmp_path):
    cfg = Config()
    cfg.hardware.simulate = True
    cfg.damper.enabled = True
    cfg.damper.stroke_time_s = 10.0
    cfg.damper.command_path = str(tmp_path / "damper")
    cfg.safety.estop_path = str(tmp_path / "estop")
    cfg.safety.heartbeat_path = str(tmp_path / "hb")

    damper = SimulatedDamper(stroke_time_s=10.0)
    ctrl = KilnController(
        cfg, damper=damper, state_path=str(tmp_path / "state.json")
    )
    ctrl.start()

    (tmp_path / "damper").write_text("40")
    last = None
    for i in range(30):
        last = ctrl.tick(now=1000.0 + i)
    assert last.damper_enabled is True
    assert abs(last.damper_target - 40.0) < 1e-6
    assert abs(last.damper_position - 40.0) < 1.0


def test_controller_without_damper_reports_disabled(tmp_path):
    cfg = Config()
    cfg.hardware.simulate = True
    cfg.safety.estop_path = str(tmp_path / "estop")
    cfg.safety.heartbeat_path = str(tmp_path / "hb")
    ctrl = KilnController(cfg, state_path=str(tmp_path / "state.json"))
    ctrl.start()
    state = ctrl.tick(now=1000.0)
    assert state.damper_enabled is False
    assert state.damper_position is None
