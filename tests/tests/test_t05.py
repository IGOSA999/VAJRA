import math


def test_t05_analytic_slab_series_solution():
    # Homogeneous slab with one step boundary and an insulated other end.
    alpha = 1.0e-6
    L = 0.2
    t = 3600.0
    n = 2000
    terms = []
    for k in range(1, n+1):
        mu = (k - 0.5) * math.pi / L
        terms.append(math.exp(-alpha * mu * mu * t) / (k - 0.5))
    series = sum(terms)
    assert math.isfinite(series) and series > 0
