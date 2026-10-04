from copy import deepcopy
from vajra.api import default_design, MATERIALS, GLAZING
from vajra.solver import simulate
from vajra.weather import synthetic_leh


def test_t07_direction_checks():
    wf = synthetic_leh(7)
    d0 = default_design()
    d1 = deepcopy(d0)
    d1["constructions"]["wall"] = [{"material":"stone_masonry","mm":300},{"material":"mineral_wool","mm":150}]
    h0 = simulate(d0, wf, MATERIALS, GLAZING, 30, "heater")["summary"]["heating_kwh"]
    h1 = simulate(d1, wf, MATERIALS, GLAZING, 30, "heater")["summary"]["heating_kwh"]
    assert h1 <= h0
