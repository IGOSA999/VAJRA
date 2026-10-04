import math
from pathlib import Path

from vajra.api import MATERIALS
from vajra.materials import load_materials


def test_t01_steady_state_u_value():
    mats = load_materials(MATERIALS)
    layers = [(mats["stone_masonry"], 0.3), (mats["mineral_wool"], 0.1)]
    r = 0.13 + sum(dx / m.lambda_w_mk for m, dx in layers) + 0.04
    u = 1 / r
    dt = 20.0
    q = u * dt
    assert abs(q - u * dt) / q < 0.005
