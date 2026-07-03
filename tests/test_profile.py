from kiln_controller.control.profile import FiringProfile


def test_empty_profile_holds_start_temp():
    p = FiringProfile.from_tuples([], start_temp_c=22.0)
    assert p.setpoint() == 22.0
    assert p.finished


def test_ramp_midpoint():
    # Ramp 22 -> 622 at 3600 C/hr (== 1 C/s): 600 C span == 600 s.
    p = FiringProfile.from_tuples([(622.0, 3600.0, 0.0)], start_temp_c=22.0)
    p.advance(300.0)
    assert abs(p.setpoint() - 322.0) < 1.0


def test_hold_after_ramp():
    p = FiringProfile.from_tuples([(100.0, 3600.0, 10.0)], start_temp_c=0.0)
    p.advance(100.0)  # end of ramp
    assert abs(p.setpoint() - 100.0) < 1e-6
    p.advance(300.0)  # into the hold
    assert abs(p.setpoint() - 100.0) < 1e-6


def test_instant_ramp_when_rate_zero():
    p = FiringProfile.from_tuples([(500.0, 0.0, 0.0)], start_temp_c=20.0)
    p.advance(0.1)
    assert p.setpoint() == 500.0


def test_total_duration():
    p = FiringProfile.from_tuples([(3600.0, 3600.0, 1.0)], start_temp_c=0.0)
    # ramp 3600 s + hold 60 s
    assert abs(p.total_duration_s() - 3660.0) < 1e-6
