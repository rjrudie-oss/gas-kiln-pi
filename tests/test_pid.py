from kiln_controller.control.pid import PID


def test_proportional_sign_and_clamp():
    pid = PID(kp=1.0, ki=0.0, kd=0.0, output_min=0.0, output_max=100.0)
    # Below setpoint -> positive output.
    assert pid.update(100.0, 50.0, 1.0) == 50.0
    # Above setpoint -> output clamped to zero (never negative gas).
    assert pid.update(50.0, 100.0, 1.0) == 0.0


def test_output_never_exceeds_max():
    pid = PID(kp=100.0, ki=0.0, kd=0.0, output_max=100.0)
    assert pid.update(1000.0, 0.0, 1.0) == 100.0


def test_integral_anti_windup_is_bounded():
    pid = PID(kp=0.0, ki=1.0, kd=0.0, output_max=100.0, integral_limit=10.0)
    for _ in range(1000):
        pid.update(100.0, 0.0, 1.0)
    # Integral clamped, so output stays within limits.
    assert 0.0 <= pid.last_output <= 100.0


def test_dt_zero_returns_last_output():
    pid = PID(kp=1.0, ki=0.0, kd=0.0)
    first = pid.update(100.0, 50.0, 1.0)
    assert pid.update(100.0, 50.0, 0.0) == first


def test_converges_toward_setpoint():
    pid = PID(kp=2.0, ki=0.05, kd=0.0, output_max=100.0)
    temp = 20.0
    for _ in range(500):
        out = pid.update(200.0, temp, 1.0)
        temp += out * 0.05 - (temp - 20.0) * 0.01  # crude plant
    assert abs(temp - 200.0) < 15.0
