import math


def test_t06_lumped_rc_limit():
    r = 2.0
    c = 10000.0
    t = 7200.0
    t0 = 5.0
    tamb = -5.0
    expected = tamb + (t0 - tamb) * math.exp(-t/(r*c))
    assert -5 < expected < 5
    assert abs((expected - tamb) / (t0 - tamb) - math.exp(-t/(r*c))) < 1e-12
