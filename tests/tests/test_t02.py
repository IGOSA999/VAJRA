from vajra.api import default_design, MATERIALS, GLAZING
from vajra.solver import simulate
from vajra.weather import synthetic_leh


def test_t02_energy_balance():
    r_free = simulate(default_design(), synthetic_leh(4), MATERIALS, GLAZING, 30, "free")
    r_heat = simulate(default_design(), synthetic_leh(4), MATERIALS, GLAZING, 30, "heater")
    assert r_free["summary"]["max_energy_balance_ratio"] < 0.005
    assert r_heat["summary"]["max_energy_balance_ratio"] < 0.005
