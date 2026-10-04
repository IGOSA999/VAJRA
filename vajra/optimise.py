from __future__ import annotations

from copy import deepcopy
import math
from time import perf_counter

import numpy as np
import pandas as pd
from scipy.stats import qmc

from .solver import simulate

WALL_MATERIALS = ["stone_masonry", "concrete_dense", "fired_clay_brick", "rammed_earth", "adobe", "timber"]
INSULATION_OPTIONS = [0, 50, 100, 150]
VARIABLES = {
    "wall_build_up": [(m, ins) for m in WALL_MATERIALS for ins in INSULATION_OPTIONS],
    "orientation": [0, 45, 90, 135, 180, 225, 270, 315],
    "glazing_fraction": [0.0, 0.05, 0.10, 0.15, 0.20, 0.30],
    "glazing": ["single_clear", "double_clear", "double_low_e"],
    "night_cover": [False, True],
    "mass": ["none", "stone", "water", "pcm"],
    "infiltration": [0.2, 0.5, 1.0],
    "aspect": [1.0, 1.5, 2.0],
    "roof": ["flat", "mono_pitch"],
}


def _categorical_sequence(n: int, levels: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    seq = np.floor((np.arange(n) + rng.random()) * levels / n).astype(int)
    rng.shuffle(seq)
    return seq


def generate_candidates(base: dict, count: int, seed: int = 20261003) -> list[dict]:
    if count <= 0:
        return []
    keys = list(VARIABLES)
    sampler = qmc.LatinHypercube(d=len(keys), seed=seed)
    sample = sampler.random(count)
    out = []
    for i, row in enumerate(sample):
        indexes = [min(len(VARIABLES[key]) - 1, int(row[j] * len(VARIABLES[key]))) for j, key in enumerate(keys)]
        if i < len(VARIABLES["wall_build_up"]):
            indexes[0] = i
        vals = {k: VARIABLES[k][indexes[j]] for j, k in enumerate(keys)}
        d = deepcopy(base)
        area = float(base["geometry"]["length_m"]) * float(base["geometry"]["width_m"])
        ratio = vals["aspect"]
        width = math.sqrt(area / ratio)
        length = area / width
        d["name"] = f"design_{i:04d}"
        d["geometry"]["length_m"] = length
        d["geometry"]["width_m"] = width
        d["geometry"]["azimuth_deg"] = vals["orientation"]
        d["geometry"]["roof"] = {
            "type": vals["roof"], "pitch_deg": 15 if vals["roof"] == "mono_pitch" else 0, "high_side": "N"
        }
        wall_material, insulation_mm = vals["wall_build_up"]
        d["constructions"]["wall"] = ([{"material": "mineral_wool", "mm": insulation_mm}] if insulation_mm else []) + [{"material": wall_material, "mm": 300}]
        facade_area = width * float(base["geometry"]["wall_height_m"])
        glazing_area = vals["glazing_fraction"] * facade_area
        win_width = min(width * 0.95, math.sqrt(max(glazing_area, 0.0))) if glazing_area else 0.0
        win_height = min(float(base["geometry"]["wall_height_m"]) * 0.8, glazing_area / max(win_width, 1e-9)) if win_width else 0.0
        d["openings"] = [] if not glazing_area else [{
            "facade": "main", "width_m": win_width, "height_m": win_height, "glazing": vals["glazing"],
            "night_cover": {"r_m2k_per_w": 0.8, "from_hour": 17, "to_hour": 9} if vals["night_cover"] else {},
        }]
        d["air"]["infiltration_ach"] = vals["infiltration"]
        if vals["mass"] == "stone":
            d["interior_mass"] = None
            d["constructions"]["floor"] = [{"material": "stone_masonry", "mm": 100}]
        elif vals["mass"] == "water":
            d["interior_mass"] = {"material": "water", "kg": 500, "surface_area_m2": 5.0, "h_inside_w_m2k": 2.5}
            # Keep the JSON field spelling used by the solver contract.
        elif vals["mass"] == "pcm":
            d["interior_mass"] = {
                "material": "pcm_paraffin", "kg": 50, "surface_area_m2": 5.0, "h_inside_w_m2k": 2.5,
                "latent_heat_j_kg": 200000, "melt_low_c": 16, "melt_high_c": 20,
            }
        else:
            d["interior_mass"] = None
        out.append(d)
    return out


def _candidate(base: dict, i: int, seed: int = 20261003) -> dict:
    return generate_candidates(base, max(24, i + 1), seed=seed)[i]


def _row_from_runs(d, free, heater):
    return {
        "name": d.get("name", "baseline"),
        "heating_kwh": round(heater["summary"]["heating_kwh"], 3),
        "heating_kwh_per_m2": round(heater["summary"]["heating_kwh_per_m2"], 3),
        "comfort_hours": round(free["summary"]["comfort_hours"], 2),
        "overheat_degree_hours": round(free["summary"]["overheat_degree_hours"], 2),
        "score": round(heater["summary"]["heating_kwh"] + free["summary"]["overheat_degree_hours"], 3),
        "orientation_deg": d["geometry"]["azimuth_deg"],
        "wall_material": d["constructions"]["wall"][-1]["material"],
        "wall_insulation_mm": next((x["mm"] for x in d["constructions"]["wall"] if x["material"] == "mineral_wool"), 0),
        "insulation_mm": next((x["mm"] for x in d["constructions"]["wall"] if x["material"] == "mineral_wool"), 0),
        "glazing": d["openings"][0]["glazing"] if d.get("openings") else "none",
    }


def compare_materials(base: dict, weather, materials_path, glazing_path, insulation_mm: int = 100) -> list[dict]:
    rows = []
    for material in WALL_MATERIALS:
        d = deepcopy(base)
        d["name"] = f"material_{material}"
        wall = []
        if insulation_mm > 0:
            wall.append({"material": "mineral_wool", "mm": insulation_mm})
        wall.append({"material": material, "mm": 300})
        d["constructions"]["wall"] = wall
        free = simulate(d, weather, materials_path, glazing_path, dt_minutes=60, run="free")
        heater = simulate(d, weather, materials_path, glazing_path, dt_minutes=60, run="heater")
        row = _row_from_runs(d, free, heater)
        row["comparison"] = "wall material at fixed 300 mm + fixed outside insulation"
        rows.append(row)
    return rows


def _weather_windows(weather, days: int = 10):
    frame = weather.frame.sort_index()
    daily = frame["t_air_c"].resample("1D").mean()
    cold_days = daily.nsmallest(days).index
    warm = frame["ghi_wm2"].resample("1D").sum().sort_values(ascending=False)
    # Prefer warm-season dates by selecting the warmest quartile by mean temperature, then highest solar.
    warm_daily = frame["t_air_c"].resample("1D").mean()
    warm_cut = warm_daily.quantile(0.60)
    warm_candidates = warm[warm_daily.reindex(warm.index).fillna(-1) >= warm_cut]
    warm_days = warm_candidates.head(days).index

    def slice_days(day_index):
        pieces = []
        for day in day_index:
            if frame.index.tz is not None:
                start = pd.Timestamp(day).tz_localize(frame.index.tz) if pd.Timestamp(day).tzinfo is None else pd.Timestamp(day).tz_convert(frame.index.tz)
            else:
                start = pd.Timestamp(day)
            end = start + pd.Timedelta(days=1)
            part = frame.loc[(frame.index >= start) & (frame.index < end)]
            if len(part):
                pieces.append(part)
        return type(weather)(pd.concat(pieces).sort_index(), dict(weather.meta)) if pieces else weather
    return slice_days(cold_days), slice_days(warm_days)


def compare_designs(base: dict, weather, materials_path, glazing_path, candidate_count: int = 24, seed: int = 20261003) -> list[dict]:
    out = []
    baseline = deepcopy(base)
    baseline["name"] = base.get("name", "baseline")
    free = simulate(baseline, weather, materials_path, glazing_path, dt_minutes=60, run="free")
    heater = simulate(baseline, weather, materials_path, glazing_path, dt_minutes=60, run="heater")
    out.append(_row_from_runs(baseline, free, heater))
    for i in range(candidate_count):
        d = _candidate(base, i, seed=seed)
        free = simulate(d, weather, materials_path, glazing_path, dt_minutes=60, run="free")
        heater = simulate(d, weather, materials_path, glazing_path, dt_minutes=60, run="heater")
        out.append(_row_from_runs(d, free, heater))
    out.sort(key=lambda x: (x["score"], x["heating_kwh"], x["name"]))
    return out


def _select_stage_2_finalists(screening: list[tuple[float, dict]], baseline: dict, count: int = 20) -> list[dict]:
    """Keep the named baseline plus the best non-baseline screening candidates."""
    nonbaseline = [d for _, d in screening if d is not baseline]
    return [baseline] + nonbaseline[:count]


def optimise_two_stage(base: dict, weather, materials_path, glazing_path, candidate_count: int = 1000, seed: int = 20261003) -> dict:
    cold, sunny = _weather_windows(weather, 10)
    baseline = deepcopy(base)
    baseline["name"] = base.get("name", "baseline")
    candidates = [baseline] + generate_candidates(base, candidate_count, seed=seed)
    t0 = perf_counter()
    screening = []
    for d in candidates:
        scores = []
        for wf in (cold, sunny):
            free = simulate(d, wf, materials_path, glazing_path, dt_minutes=60, run="free")
            heater = simulate(d, wf, materials_path, glazing_path, dt_minutes=60, run="heater")
            scores.append(heater["summary"]["heating_kwh"] + free["summary"]["overheat_degree_hours"])
        screening.append((sum(scores) / len(scores), d))
    elapsed = max(perf_counter() - t0, 1e-9)
    screening.sort(key=lambda x: (x[0], x[1]["name"]))
    finalists = _select_stage_2_finalists(screening, baseline, count=20)
    confirmed = []
    for d in finalists:
        free = simulate(d, weather, materials_path, glazing_path, dt_minutes=60, run="free")
        heater = simulate(d, weather, materials_path, glazing_path, dt_minutes=60, run="heater")
        confirmed.append(_row_from_runs(d, free, heater))
    confirmed.sort(key=lambda x: (x["score"], x["heating_kwh"], x["name"]))
    return {
        "screening": confirmed,
        "screening_seconds": elapsed,
        "screening_designs_per_second": len(candidates) / elapsed,
        "seed": seed,
        "candidate_count": candidate_count,
        "stage_1_windows": {"coldest_days": 10, "sunniest_warm_days": 10},
    }
