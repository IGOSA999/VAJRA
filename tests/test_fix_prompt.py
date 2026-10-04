from __future__ import annotations

import numpy as np

from copy import deepcopy
from pathlib import Path
import subprocess
import re

import pandas as pd
import pytest

from vajra.api import default_design, MATERIALS, GLAZING
from vajra.optimise import _candidate, compare_materials, compare_designs, generate_candidates
from vajra.solar import PVLIB_AVAILABLE, plane_of_array, plane_of_array_fallback, solar_position
from vajra.solver import simulate, validate_design
from vajra.weather import synthetic_leh

ROOT = Path(__file__).resolve().parents[1]


def _swing(result):
    s = pd.Series(result["series"]["t_air_in_c"], index=pd.to_datetime(result["series"]["time"], utc=True))
    return float(s.max() - s.min())


def test_fix_01_requirements_declares_multipart():
    req = (ROOT / "requirements.txt").read_text()
    assert "python-multipart" in req


def test_fix_02_water_mass_changes_daily_swing():
    wf = synthetic_leh(3)
    base = default_design()
    mass = deepcopy(base)
    mass["interior_mass"] = {"material": "water", "kg": 500, "surface_area_m2": 5.0, "h_inside_w_m2k": 2.5}
    a = simulate(base, wf, MATERIALS, GLAZING, 30, "free")
    b = simulate(mass, wf, MATERIALS, GLAZING, 30, "free")
    assert _swing(b) < _swing(a)


def test_fix_02_pcm_latent_heat_changes_minimum_and_closure():
    wf = synthetic_leh(3)
    sensible = default_design()
    sensible["interior_mass"] = {"material": "pcm_paraffin", "kg": 50, "surface_area_m2": 5.0, "h_inside_w_m2k": 2.5, "latent_heat_j_kg": 0, "melt_low_c": -20, "melt_high_c": 0}
    latent = deepcopy(sensible)
    latent["interior_mass"]["latent_heat_j_kg"] = 200000
    a = simulate(sensible, wf, MATERIALS, GLAZING, 30, "free")
    b = simulate(latent, wf, MATERIALS, GLAZING, 30, "free")
    assert b["summary"]["t_min_c"] > a["summary"]["t_min_c"]
    assert b["summary"]["max_boundary_energy_closure_ratio"] < 0.005
    assert b["summary"]["max_mass_iterations"] >= 2


def test_fix_02_unknown_design_field_rejected():
    d = default_design()
    d["unused_feature"] = 123
    with pytest.raises(ValueError, match="Unsupported design field"):
        validate_design(d)


def test_fix_03_outside_insulation_smaller_swing():
    wf = synthetic_leh(3)
    outside = default_design()
    outside["constructions"]["wall"] = [{"material": "mineral_wool", "mm": 100}, {"material": "stone_masonry", "mm": 300}]
    inside = default_design()
    inside["constructions"]["wall"] = [{"material": "stone_masonry", "mm": 300}, {"material": "mineral_wool", "mm": 100}]
    a = simulate(outside, wf, MATERIALS, GLAZING, 30, "free")
    b = simulate(inside, wf, MATERIALS, GLAZING, 30, "free")
    assert _swing(a) < _swing(b)


def test_fix_04_candidates_cover_all_wall_build_ups():
    candidates = generate_candidates(default_design(), 24, seed=20261003)
    builds = {(c["constructions"]["wall"][-1]["material"], next((x["mm"] for x in c["constructions"]["wall"] if x["material"] == "mineral_wool"), 0)) for c in candidates}
    assert len(builds) == 24


def test_fix_04_same_seed_same_rankings():
    wf = synthetic_leh(3)
    base = default_design()
    a = compare_designs(base, wf, MATERIALS, GLAZING, candidate_count=6, seed=777)
    b = compare_designs(base, wf, MATERIALS, GLAZING, candidate_count=6, seed=777)
    assert a == b


def test_fix_04_stage_2_always_keeps_baseline():
    baseline = {"name": "baseline"}
    screening = [(float(i), {"name": f"design_{i:04d}"}) for i in range(25)] + [(999.0, baseline)]
    from vajra.optimise import _select_stage_2_finalists
    finalists = _select_stage_2_finalists(screening, baseline, count=20)
    assert len(finalists) == 21
    assert finalists[0] is baseline
    assert baseline in finalists
    assert [d["name"] for d in finalists[1:]] == [f"design_{i:04d}" for i in range(20)]


def test_fix_04_material_only_comparison_changes_heating_energy():
    wf = synthetic_leh(3)
    rows = compare_materials(default_design(), wf, MATERIALS, GLAZING, insulation_mm=100)
    energies = [r["heating_kwh"] for r in rows]
    assert len(rows) == 6
    assert len({round(x, 6) for x in energies}) > 1


def test_fix_05_slop_scan_requires_real_bundled_fonts():
    result = subprocess.run(["python", "scripts/slop_scan.py"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    for name in ["IBMPlexSans-Regular.woff2", "IBMPlexSans-SemiBold.woff2", "IBMPlexMono-Regular.woff2", "SourceSerif4-Regular.woff2"]:
        assert (ROOT / "web/fonts" / name).is_file()
        assert (ROOT / "web/fonts" / name).stat().st_size > 1000


def test_fix_06_boundary_flow_is_t2_criterion():
    r = simulate(default_design(), synthetic_leh(4), MATERIALS, GLAZING, 30, "heater")
    assert r["summary"]["max_boundary_energy_closure_ratio"] < 0.005
    assert r["summary"]["max_equation_balance_ratio"] < 1e-9


@pytest.mark.skipif(not PVLIB_AVAILABLE, reason="pvlib not installed in current environment")
def test_fix_07_pvlib_crosscheck_full_year():
    wf = synthetic_leh(365)
    idx = wf.frame.index
    zen, _ = solar_position(idx, 34.1526, 77.5771)
    import pvlib
    pos = pvlib.solarposition.get_solarposition(idx, 34.1526, 77.5771)
    diff = np.abs((90.0 - zen) - pos["apparent_elevation"].to_numpy())
    # pvlib applies refraction, so the two differ most within a few degrees of the horizon. Judge daytime hours.
    elevation_diff = float(diff[(90.0 - zen) > 5].max())
    fallback = plane_of_array_fallback(90, 180, idx, wf.frame.ghi_wm2.to_numpy(), wf.frame.dhi_wm2.to_numpy(), wf.frame.dni_wm2.to_numpy(), 34.1526, 77.5771)
    pos2 = pvlib.solarposition.get_solarposition(idx, 34.1526, 77.5771)
    total = pvlib.irradiance.get_total_irradiance(90, 180, pos2["apparent_zenith"].to_numpy(), pos2["azimuth"].to_numpy(), wf.frame.dni_wm2.to_numpy(), wf.frame.ghi_wm2.to_numpy(), wf.frame.dhi_wm2.to_numpy(), dni_extra=np.asarray(pvlib.irradiance.get_extra_radiation(idx), dtype=float), albedo=0.2, model="haydavies")
    poa = np.asarray(total["poa_global"], dtype=float)
    mask = poa > 20
    poa_mape = float((abs(fallback[mask] - poa[mask]) / poa[mask]).mean())
    annual_ratio = float(fallback.sum() / poa.sum())
    print(f"elevation diff {elevation_diff:.3f} deg, hourly POA MAPE {poa_mape:.4f}, annual ratio {annual_ratio:.4f}")
    assert elevation_diff < 0.5
    assert abs(annual_ratio - 1.0) < 0.01


