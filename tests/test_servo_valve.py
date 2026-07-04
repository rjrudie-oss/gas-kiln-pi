from kiln_controller.hardware.valve import ModulatingValve, ServoValve


def _bare_servo(closed_angle=-90.0, open_angle=90.0):
    """A ServoValve without touching gpiozero (skip __init__ hardware setup)."""
    s = object.__new__(ServoValve)
    s._closed_angle = closed_angle
    s._open_angle = open_angle
    s._commanded = 0.0
    return s


def test_angle_mapping_endpoints_and_midpoint():
    s = _bare_servo(closed_angle=-90.0, open_angle=90.0)
    assert s._angle_for(0.0) == -90.0
    assert s._angle_for(100.0) == 90.0
    assert s._angle_for(50.0) == 0.0


def test_angle_mapping_respects_custom_range():
    s = _bare_servo(closed_angle=0.0, open_angle=45.0)
    assert s._angle_for(0.0) == 0.0
    assert s._angle_for(100.0) == 45.0
    assert abs(s._angle_for(50.0) - 22.5) < 1e-9


class FakeElement:
    """Records set_percent / close calls for a valve element."""

    def __init__(self):
        self.commanded_percent = 0.0
        self.calls = []

    def set_percent(self, percent):
        self.commanded_percent = percent
        self.calls.append(("set", percent))

    def close(self):
        self.commanded_percent = 0.0
        self.calls.append(("close", None))


def test_modulating_holds_solenoid_open_and_throttles_servo():
    servo, shutoff = FakeElement(), FakeElement()
    v = ModulatingValve(servo, shutoff)
    # Construction closes both as a known-safe starting point.
    assert servo.calls[-1] == ("close", None)
    assert shutoff.calls[-1] == ("close", None)

    v.set_percent(37.0)
    # Servo throttles to the command; solenoid is held fully open.
    assert servo.commanded_percent == 37.0
    assert shutoff.commanded_percent == 100.0
    assert v.commanded_percent == 37.0


def test_modulating_close_shuts_both():
    servo, shutoff = FakeElement(), FakeElement()
    v = ModulatingValve(servo, shutoff)
    v.set_percent(80.0)
    v.close()
    assert servo.commanded_percent == 0.0
    assert shutoff.commanded_percent == 0.0
    assert v.commanded_percent == 0.0


def test_modulating_clamps_out_of_range():
    servo, shutoff = FakeElement(), FakeElement()
    v = ModulatingValve(servo, shutoff)
    v.set_percent(150.0)
    assert servo.commanded_percent == 100.0
    v.set_percent(-10.0)
    assert servo.commanded_percent == 0.0
    # Even at 0 % throttle the safety solenoid stays open while firing.
    assert shutoff.commanded_percent == 100.0
