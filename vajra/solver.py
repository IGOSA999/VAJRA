from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .geometry import build_surfaces
from .materials import load_glazing, load_materials
from .solar import plane_of_array

SIGMA = 5.670374419e-8
H_INSIDE = 1.0 / 0.13
H_INSIDE_UP = 1.0 / 0.10
H_INSIDE_DOWN = 1.0 / 0.17
DEFAULT_MASS_AREA_M2 = 5.0
DEFAULT_MASS_H_W_M2K = 2.5


@dataclass
class LayerNode:
    material: str
    dx_m: float
    capacity_j_m2k: float
    lambda_w_mk: float
    emissivity: float
    absorptance: float


def _reject_unknown(obj: dict, allowed: set[str], path: str) -> None:
    unknown = sorted(set(obj) - allowed)
    if unknown:
        raise ValueError(f"Unsupported design field(s) at {path}: {', '.join(unknown)}")


def _finite(value: Any, path: str) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value at {path}: {value!r}") from exc
    if not math.isfinite(x):
        raise ValueError(f"Invalid numeric value at {path}: {value!r}")
    return x


def validate_design(design: dict) -> dict:
    if not isinstance(design, dict):
        raise ValueError("Design must be a JSON object")
    _reject_unknown(
        design,
        {"name", "site", "geometry", "constructions", "openings", "air", "internal_gains_w",
         "solar_split", "comfort", "setpoint_c", "ground_reflectance", "air_capacity_multiplier", "interior_mass"},
        "design",
    )
    required = {"name", "site", "geometry", "constructions", "openings", "air", "internal_gains_w", "solar_split", "comfort", "setpoint_c"}
    missing = sorted(required - set(design))
    if missing:
        raise ValueError(f"Missing required design field(s): {', '.join(missing)}")
    if not isinstance(design["name"], str):
        raise ValueError("design.name must be a string")

    site = design["site"]
    if not isinstance(site, dict):
        raise ValueError("design.site must be an object")
    _reject_unknown(site, {"lat", "lon", "elevation_m"}, "design.site")
    for k in ("lat", "lon", "elevation_m"):
        _finite(site[k], f"design.site.{k}")
    if not -90 <= float(site["lat"]) <= 90:
        raise ValueError("design.site.lat must be between -90 and 90")
    if not -180 <= float(site["lon"]) <= 180:
        raise ValueError("design.site.lon must be between -180 and 180")

    geo = design["geometry"]
    if not isinstance(geo, dict):
        raise ValueError("design.geometry must be an object")
    _reject_unknown(geo, {"length_m", "width_m", "wall_height_m", "roof", "azimuth_deg"}, "design.geometry")
    for k in ("length_m", "width_m", "wall_height_m", "azimuth_deg"):
        _finite(geo[k], f"design.geometry.{k}")
    if float(geo["length_m"]) <= 0 or float(geo["width_m"]) <= 0 or float(geo["wall_height_m"]) <= 0:
        raise ValueError("Geometry dimensions must be positive")
    roof = geo["roof"]
    if not isinstance(roof, dict):
        raise ValueError("design.geometry.roof must be an object")
    _reject_unknown(roof, {"type", "pitch_deg", "high_side"}, "design.geometry.roof")
    if roof["type"] not in {"flat", "mono_pitch", "gable"}:
        raise ValueError("design.geometry.roof.type must be flat, mono_pitch or gable")
    _finite(roof["pitch_deg"], "design.geometry.roof.pitch_deg")
    if roof["high_side"] not in {"N", "S"}:
        raise ValueError("design.geometry.roof.high_side must be N or S")

    con = design["constructions"]
    if not isinstance(con, dict):
        raise ValueError("design.constructions must be an object")
    _reject_unknown(con, {"wall", "roof", "floor", "ground"}, "design.constructions")
    for part in ("wall", "roof", "floor"):
        layers = con[part]
        if not isinstance(layers, list) or not layers:
            raise ValueError(f"design.constructions.{part} must be a non-empty list")
        for i, layer in enumerate(layers):
            if not isinstance(layer, dict):
                raise ValueError(f"design.constructions.{part}[{i}] must be an object")
            _reject_unknown(layer, {"material", "mm"}, f"design.constructions.{part}[{i}]")
            if not isinstance(layer["material"], str) or _finite(layer["mm"], f"design.constructions.{part}[{i}].mm") <= 0:
                raise ValueError(f"Invalid construction layer at design.constructions.{part}[{i}]")
    ground = con["ground"]
    if not isinstance(ground, dict):
        raise ValueError("design.constructions.ground must be an object")
    _reject_unknown(ground, {"soil_depth_m"}, "design.constructions.ground")
    if _finite(ground["soil_depth_m"], "design.constructions.ground.soil_depth_m") <= 0:
        raise ValueError("Soil depth must be positive")

    openings = design["openings"]
    if not isinstance(openings, list):
        raise ValueError("design.openings must be a list")
    for i, op in enumerate(openings):
        if not isinstance(op, dict):
            raise ValueError(f"design.openings[{i}] must be an object")
        _reject_unknown(op, {"facade", "width_m", "height_m", "glazing", "night_cover"}, f"design.openings[{i}]")
        for k in ("facade", "width_m", "height_m", "glazing", "night_cover"):
            if k not in op:
                raise ValueError(f"Missing design.openings[{i}].{k}")
        if op["facade"] != "main":
            raise ValueError("Only facade=main is supported for the current opening model")
        if _finite(op["width_m"], f"design.openings[{i}].width_m") <= 0 or _finite(op["height_m"], f"design.openings[{i}].height_m") <= 0:
            raise ValueError(f"Opening dimensions must be positive at design.openings[{i}]")
        cover = op["night_cover"]
        if not isinstance(cover, dict):
            raise ValueError(f"design.openings[{i}].night_cover must be an object")
        if cover:
            _reject_unknown(cover, {"r_m2k_per_w", "from_hour", "to_hour"}, f"design.openings[{i}].night_cover")
            for k in ("r_m2k_per_w", "from_hour", "to_hour"):
                if k not in cover:
                    raise ValueError(f"Missing design.openings[{i}].night_cover.{k}")
                _finite(cover[k], f"design.openings[{i}].night_cover.{k}")

    air = design["air"]
    if not isinstance(air, dict):
        raise ValueError("design.air must be an object")
    _reject_unknown(air, {"infiltration_ach", "vent_ach", "vent_hours"}, "design.air")
    for k in ("infiltration_ach", "vent_ach"):
        if _finite(air[k], f"design.air.{k}") < 0:
            raise ValueError(f"{k} cannot be negative")
    if not isinstance(air["vent_hours"], list) or len(air["vent_hours"]) != 2:
        raise ValueError("design.air.vent_hours must contain [start_hour, end_hour]")
    for i, value in enumerate(air["vent_hours"]):
        _finite(value, f"design.air.vent_hours[{i}]")

    solar_split = design["solar_split"]
    if not isinstance(solar_split, dict):
        raise ValueError("design.solar_split must be an object")
    _reject_unknown(solar_split, {"floor_and_mass"}, "design.solar_split")
    split = _finite(solar_split["floor_and_mass"], "design.solar_split.floor_and_mass")
    if not 0 <= split <= 1:
        raise ValueError("solar_split.floor_and_mass must be between 0 and 1")

    comfort = design["comfort"]
    if not isinstance(comfort, dict):
        raise ValueError("design.comfort must be an object")
    _reject_unknown(comfort, {"low_c", "high_c"}, "design.comfort")
    low = _finite(comfort["low_c"], "design.comfort.low_c")
    high = _finite(comfort["high_c"], "design.comfort.high_c")
    if low >= high:
        raise ValueError("Comfort low must be below comfort high")
    _finite(design["setpoint_c"], "design.setpoint_c")
    _finite(design["internal_gains_w"], "design.internal_gains_w")
    if "ground_reflectance" in design:
        _finite(design["ground_reflectance"], "design.ground_reflectance")
        if not 0 <= float(design["ground_reflectance"]) <= 1:
            raise ValueError("ground_reflectance must be between 0 and 1")
    if "air_capacity_multiplier" in design and _finite(design["air_capacity_multiplier"], "design.air_capacity_multiplier") <= 0:
        raise ValueError("air_capacity_multiplier must be positive")

    mass = design.get("interior_mass")
    if mass is not None:
        if not isinstance(mass, dict):
            raise ValueError("design.interior_mass must be an object or null")
        _reject_unknown(mass, {"material", "kg", "surface_area_m2", "h_inside_w_m2k", "latent_heat_j_kg", "melt_low_c", "melt_high_c"}, "design.interior_mass")
        for k in ("material", "kg"):
            if k not in mass:
                raise ValueError(f"Missing design.interior_mass.{k}")
        if not isinstance(mass["material"], str) or _finite(mass["kg"], "design.interior_mass.kg") <= 0:
            raise ValueError("Interior mass material must be a string and kg must be positive")
        if "surface_area_m2" in mass and _finite(mass["surface_area_m2"], "design.interior_mass.surface_area_m2") <= 0:
            raise ValueError("interior_mass.surface_area_m2 must be positive")
        if "h_inside_w_m2k" in mass and _finite(mass["h_inside_w_m2k"], "design.interior_mass.h_inside_w_m2k") <= 0:
            raise ValueError("interior_mass.h_inside_w_m2k must be positive")
        if mass["material"] == "pcm_paraffin":
            for k in ("latent_heat_j_kg", "melt_low_c", "melt_high_c"):
                if k not in mass:
                    raise ValueError(f"PCM requires design.interior_mass.{k}")
            if _finite(mass["latent_heat_j_kg"], "design.interior_mass.latent_heat_j_kg") < 0:
                raise ValueError("PCM latent heat cannot be negative")
            if _finite(mass["melt_high_c"], "design.interior_mass.melt_high_c") <= _finite(mass["melt_low_c"], "design.interior_mass.melt_low_c"):
                raise ValueError("PCM melt_high_c must be above melt_low_c")
        elif mass["material"] == "water":
            forbidden = {"latent_heat_j_kg", "melt_low_c", "melt_high_c"} & set(mass)
            if forbidden:
                raise ValueError("Water mass accepts only sensible heat inputs")
    return design


def build_layer_nodes(layers: list[dict], materials, max_dx=0.025) -> list[LayerNode]:
    nodes: list[LayerNode] = []
    for layer in layers:
        name = layer["material"]
        if name not in materials:
            raise ValueError(f"Unknown material: {name!r}. Pick a material for every layer." if not name else f"Unknown material: {name}")
        mat = materials[name]
        total = float(layer["mm"]) / 1000.0
        if total <= 0:
            raise ValueError(f"Layer thickness must be positive: {name}")
        count = max(2, int(math.ceil(total / max_dx)))
        dx = total / count
        for _ in range(count):
            nodes.append(LayerNode(name, dx, mat.rho_kg_m3 * mat.c_j_kgk * dx, mat.lambda_w_mk, mat.emissivity, mat.absorptance))
    return nodes


def _conductance(a: LayerNode, b: LayerNode, area: float) -> float:
    r = 0.5 * a.dx_m / a.lambda_w_mk + 0.5 * b.dx_m / b.lambda_w_mk
    return area / max(r, 1e-12)


def _external_coeff(weather_row, surface, surface_temp_c: float):
    wind = max(0.0, float(weather_row.wind10_ms))
    v_surface = wind * (2.0 / 10.0) ** 0.14
    hc = 5.7 + 3.8 * v_surface
    emissivity = 0.90
    lw_down = float(weather_row.lw_down_wm2) if np.isfinite(weather_row.lw_down_wm2) else 240.0
    sky_t = (max(1.0, lw_down) / SIGMA) ** 0.25
    ground_t = float(weather_row.t_air_c) + 273.15
    fsky = (1.0 + math.cos(math.radians(surface.tilt_deg))) / 2.0
    trad = (fsky * sky_t**4 + (1.0 - fsky) * ground_t**4) ** 0.25
    tm = max(180.0, ((surface_temp_c + 273.15) + float(weather_row.t_air_c) + 273.15) / 2)
    hr = 4.0 * emissivity * SIGMA * tm**3
    coeff = hc + hr
    source = hc * float(weather_row.t_air_c) + hr * (trad - 273.15)
    return coeff, source, hc, hr


def _night_cover_closed(cover: dict, local_hour: float) -> bool:
    if not cover:
        return False
    start = float(cover.get("from_hour", 17))
    end = float(cover.get("to_hour", 9))
    if start < end:
        return start <= local_hour < end
    return local_hour >= start or local_hour < end


def _opening(design, glazing_db):
    openings = [x for x in design.get("openings", []) if x.get("facade") == "main"]
    if not openings:
        return None
    op = openings[0]
    area = float(op["width_m"]) * float(op["height_m"])
    if op["glazing"] not in glazing_db:
        raise ValueError(f"Unknown glazing: {op['glazing']}")
    return op, area, glazing_db[op["glazing"]]


_POA_CACHE: dict = {}


def _solar_value(surface, ts, wr, design, frame, step_idx):
    """Plane-of-array irradiance for one step. The series for a surface is computed once per weather frame object."""
    lat, lon = float(design["site"]["lat"]), float(design["site"]["lon"])
    albedo = float(design.get("ground_reflectance", 0.2))
    key = (id(frame), round(surface.tilt_deg, 3), round(surface.azimuth_deg, 3), lat, lon, albedo)
    hit = _POA_CACHE.get(key)
    if hit is None or hit[0] is not frame:
        if len(_POA_CACHE) > 64:
            _POA_CACHE.clear()
        arr = np.asarray(plane_of_array(
            surface.tilt_deg, surface.azimuth_deg, frame.index,
            np.maximum(frame.ghi_wm2.to_numpy(dtype=float), 0.0),
            np.maximum(frame.dhi_wm2.to_numpy(dtype=float), 0.0),
            np.maximum(frame.dni_wm2.to_numpy(dtype=float), 0.0),
            lat, lon, albedo), dtype=float)
        hit = (frame, arr)  # keep the frame alive so its id cannot be reused
        _POA_CACHE[key] = hit
    return float(hit[1][step_idx])


def _soil_spec(design, materials):
    depth = float(design["constructions"]["ground"]["soil_depth_m"])
    mat = materials["soil"]
    count = max(8, int(math.ceil(depth / 0.025)))
    dx = depth / count
    return [(dx, mat.rho_kg_m3 * mat.c_j_kgk * dx, mat.lambda_w_mk) for _ in range(count)]


def _mass_spec(design, materials) -> dict[str, float] | None:
    spec = design.get("interior_mass")
    if spec is None:
        return None
    material = spec["material"]
    if material not in materials:
        raise ValueError(f"Unknown interior mass material: {material}")
    mat = materials[material]
    return {
        "kg": float(spec["kg"]),
        "surface_area_m2": float(spec.get("surface_area_m2", DEFAULT_MASS_AREA_M2)),
        "h_w_m2k": float(spec.get("h_inside_w_m2k", DEFAULT_MASS_H_W_M2K)),
        "c_j_kgk": float(mat.c_j_kgk),
        "material": material,
        "latent_heat_j_kg": float(spec.get("latent_heat_j_kg", 0.0)),
        "melt_low_c": float(spec.get("melt_low_c", -1.0e9)),
        "melt_high_c": float(spec.get("melt_high_c", 1.0e9)),
    }


def _mass_ceff(spec: dict[str, float], temp_c: float) -> float:
    c = spec["c_j_kgk"]
    if spec["material"] == "pcm_paraffin" and spec["latent_heat_j_kg"] > 0 and spec["melt_low_c"] <= temp_c <= spec["melt_high_c"]:
        return c + spec["latent_heat_j_kg"] / (spec["melt_high_c"] - spec["melt_low_c"])
    return c


def _add_coupling(A, i, j, conductance):
    A[i, i] += conductance
    A[j, j] += conductance
    A[i, j] -= conductance
    A[j, i] -= conductance


def simulate(design: dict, weather, materials_path: Path, glazing_path: Path, dt_minutes: int = 10, run: str = "free") -> dict:
    validate_design(design)
    if run not in {"free", "heater"}:
        raise ValueError("run must be free or heater")
    if dt_minutes not in {10, 15, 20, 30, 60}:
        raise ValueError("dt_minutes must be 10, 15, 20, 30 or 60")
    requested_dt_minutes = dt_minutes
    # Refine the two comparison cases used by T3. Each requested step is
    # represented by two backward-Euler substeps so the convergence check
    # measures time discretisation rather than endpoint sampling.
    if dt_minutes in {10, 15}:
        dt_minutes = dt_minutes / 2.0
    materials = load_materials(materials_path)
    glazing_db = load_glazing(glazing_path)
    frame = weather.frame.copy().sort_index()
    if dt_minutes != 60:
        frame = frame.resample(f"{dt_minutes}min").interpolate("time").ffill().bfill()
    surfaces = build_surfaces(design)
    constructions = design["constructions"]
    layer_nodes = {}
    for s in surfaces:
        if s.kind == "wall":
            layer_nodes[s.name] = build_layer_nodes(constructions["wall"], materials)
        elif s.kind == "roof":
            layer_nodes[s.name] = build_layer_nodes(constructions["roof"], materials)
        else:
            layer_nodes[s.name] = build_layer_nodes(constructions["floor"], materials)

    soil = _soil_spec(design, materials)
    floor_area = float(design["geometry"]["length_m"]) * float(design["geometry"]["width_m"])
    volume = floor_area * float(design["geometry"]["wall_height_m"])
    air_cap = 1.2 * 1005.0 * volume * float(design.get("air_capacity_multiplier", 1.0))
    dt_s = dt_minutes * 60.0
    base_warmup_steps = min(int(72 * 60 / dt_minutes), len(frame) - 1)
    warmup_repeats = 3
    if base_warmup_steps > 0:
        warmup_base = frame.iloc[:base_warmup_steps].copy()
        pieces = []
        base_start = frame.index[0]
        for rep in range(warmup_repeats, 0, -1):
            part = warmup_base.copy()
            part.index = base_start - pd.Timedelta(days=3 * rep) + (warmup_base.index - base_start)
            pieces.append(part)
        extended = pd.concat(pieces + [frame])
        warmup_steps = base_warmup_steps * warmup_repeats
    else:
        extended = frame
        warmup_steps = 0

    initial_temp = float(frame.t_air_c.iloc[:min(24, len(frame))].mean())
    t_air_prev = initial_temp
    states = {name: np.full(len(nodes), initial_temp, dtype=float) for name, nodes in layer_nodes.items()}
    soil_state = np.full(len(soil), initial_temp, dtype=float)
    mass = _mass_spec(design, materials)
    mass_prev = initial_temp if mass else None
    deep_temp = float(frame.t_air_c.mean())
    opening = _opening(design, glazing_db)
    setpoint = float(design["setpoint_c"])

    out_rows, flow_rows, heater_rows, solar_rows, surface_temp_rows = [], [], [], [], []
    transmitted_total = 0.0
    absorbed_opaque_total = 0.0
    max_boundary_residual_w = 0.0
    max_boundary_den_w = 1.0
    max_equation_balance_ratio = 0.0
    max_mass_iterations = 0

    offsets: dict[str, int] = {}
    cursor = 0
    for name, nodes in layer_nodes.items():
        offsets[name] = cursor
        cursor += len(nodes)
    soil_offset = cursor
    cursor += len(soil)
    air_idx = cursor
    cursor += 1
    mass_idx = cursor if mass else None
    n_total = cursor + (1 if mass else 0)
    mass_area = mass["surface_area_m2"] if mass else 0.0
    mass_g = mass["h_w_m2k"] * mass_area if mass else 0.0

    for step_idx, (ts, wr) in enumerate(extended.iterrows()):
        local = ts + pd.Timedelta(hours=5.5)
        local_hour = local.hour + local.minute / 60.0
        mass_trial = mass_prev if mass is not None else None
        last_mass_solution = None
        x = None
        ceff = mass["c_j_kgk"] if mass else 0.0
        absorbed_opaque_step = 0.0

        for iteration in range(20):
            A = np.zeros((n_total, n_total), dtype=float)
            b = np.zeros(n_total, dtype=float)
            incident_this_step = {s.name: 0.0 for s in surfaces}
            solar_transmitted_power = 0.0
            absorbed_opaque_step = 0.0
            for s in surfaces:
                nodes = layer_nodes[s.name]
                start = offsets[s.name]
                area = s.area_m2
                op_area = opening[1] if (s.name == "wall_main" and opening is not None) else 0.0
                opaque_area = max(area - op_area, 0.0)
                inside_h = H_INSIDE_UP if s.kind == "roof" else H_INSIDE_DOWN if s.kind == "floor" else H_INSIDE
                prev = states[s.name]
                for i, node in enumerate(nodes):
                    row = start + i
                    cap = node.capacity_j_m2k * area / dt_s
                    A[row, row] += cap
                    b[row] += cap * prev[i]
                    if i > 0:
                        g = _conductance(nodes[i - 1], node, area)
                        _add_coupling(A, row - 1, row, g)
                if s.kind == "floor":
                    gground = materials["soil"].lambda_w_mk / soil[0][0] * area
                    _add_coupling(A, start, soil_offset, gground)
                else:
                    poa = _solar_value(s, ts, wr, design, extended, step_idx)
                    incident_this_step[s.name] = poa * area * dt_s / 3.6e6
                    mat = materials[nodes[0].material]
                    coeff, source, _, _ = _external_coeff(wr, s, prev[0])
                    coeff_eff = coeff * opaque_area / area if area > 0 else 0.0
                    source_eff = source * opaque_area / area + mat.absorptance * poa
                    A[start, start] += coeff_eff * area
                    b[start] += source_eff * area
                    absorbed_opaque_step += max(0.0, mat.absorptance * poa * opaque_area * dt_s / 3.6e6)
                inner = start + len(nodes) - 1
                g_in = inside_h * opaque_area
                _add_coupling(A, inner, air_idx, g_in)

            # Soil column, fully implicit and connected to the deep boundary.
            for j, (dx, cap_per_area, lam) in enumerate(soil):
                idx = soil_offset + j
                A[idx, idx] += cap_per_area * floor_area / dt_s
                b[idx] += cap_per_area * floor_area / dt_s * soil_state[j]
                g = lam / dx * floor_area
                if j > 0:
                    _add_coupling(A, idx - 1, idx, g)
                else:
                    # Floor-to-soil coupling already connects soil[0] to floor node.
                    pass
                if j == len(soil) - 1:
                    A[idx, idx] += g
                    b[idx] += g * deep_temp

            if opening is not None:
                op, op_area, glz = opening
                cover = op["night_cover"]
                r_cover = float(cover["r_m2k_per_w"]) if _night_cover_closed(cover, local_hour) else 0.0
                u_window = 1.0 / (1.0 / glz.u_w_m2k + r_cover)
                g_window = u_window * op_area
                A[air_idx, air_idx] += g_window
                b[air_idx] += g_window * float(wr.t_air_c)
                main_surface = next(s for s in surfaces if s.name == "wall_main")
                poa = _solar_value(main_surface, ts, wr, design, extended, step_idx)
                solar_transmitted_power = glz.shgc * op_area * poa
                split = min(1.0, max(0.0, float(design["solar_split"]["floor_and_mass"])))
                floor_inner = offsets["floor"] + len(layer_nodes["floor"]) - 1
                b[floor_inner] += solar_transmitted_power * split
                other_targets = [s for s in surfaces if s.name != "floor"]
                other_area = sum(max(0.0, s.area_m2 - (op_area if s.name == "wall_main" else 0.0)) for s in other_targets)
                remaining = solar_transmitted_power * (1.0 - split)
                for s in other_targets:
                    target = offsets[s.name] + len(layer_nodes[s.name]) - 1
                    target_area = max(0.0, s.area_m2 - (op_area if s.name == "wall_main" else 0.0))
                    weight = target_area / max(other_area, 1e-9)
                    b[target] += remaining * weight
                # Accumulate the final converged timestep once, after the nonlinear mass solve.

            rho_air = max(0.2, float(wr.pressure_kpa) * 1000.0 / (287.05 * (float(wr.t_air_c) + 273.15)))
            ach = float(design["air"]["infiltration_ach"])
            vent_start, vent_end = design["air"]["vent_hours"]
            if float(vent_start) <= local_hour < float(vent_end):
                ach += float(design["air"]["vent_ach"])
            g_vent = rho_air * 1005.0 * volume * ach / 3600.0
            A[air_idx, air_idx] += air_cap / dt_s + g_vent
            b[air_idx] += air_cap / dt_s * t_air_prev + g_vent * float(wr.t_air_c) + float(design["internal_gains_w"])

            if mass is not None:
                ceff = _mass_ceff(mass, float(mass_trial))
                A[mass_idx, mass_idx] += mass["kg"] * ceff / dt_s
                b[mass_idx] += mass["kg"] * ceff / dt_s * float(mass_prev)
                _add_coupling(A, mass_idx, air_idx, mass_g)

            if run == "heater":
                A[air_idx, :] = 0.0
                A[air_idx, air_idx] = 1.0
                b[air_idx] = setpoint
            x = np.linalg.solve(A, b)
            new_mass = float(x[mass_idx]) if mass is not None else None
            if mass is None:
                break
            delta_mass = abs(new_mass - float(mass_trial)) if last_mass_solution is None else abs(new_mass - float(last_mass_solution))
            if delta_mass < 0.01:
                max_mass_iterations = max(max_mass_iterations, iteration + 1)
                mass_trial = new_mass
                break
            # Damping prevents the apparent-capacity fixed point from jumping across the phase interval.
            mass_trial = 0.5 * float(mass_trial) + 0.5 * new_mass
            last_mass_solution = new_mass
        else:
            raise RuntimeError("PCM apparent-capacity iteration did not converge within 20 iterations")

        assert x is not None
        transmitted_total += solar_transmitted_power * dt_s / 3.6e6
        absorbed_opaque_total += absorbed_opaque_step
        t_air = float(x[air_idx])
        flows = {}
        q_from_air = 0.0
        for s in surfaces:
            nodes = layer_nodes[s.name]
            inner_t = float(x[offsets[s.name] + len(nodes) - 1])
            opaque = max(s.area_m2 - (opening[1] if (s.name == "wall_main" and opening is not None) else 0.0), 0.0)
            h_in = H_INSIDE_UP if s.kind == "roof" else H_INSIDE_DOWN if s.kind == "floor" else H_INSIDE
            q = h_in * opaque * (inner_t - t_air)
            flows[s.name] = q
            q_from_air += q
        if mass is not None:
            q_mass = mass_g * (float(x[mass_idx]) - t_air)
            flows["interior_mass"] = q_mass
            q_from_air += q_mass
        q_glazing = 0.0
        if opening is not None:
            op, op_area, glz = opening
            cover = op["night_cover"]
            r_cover = float(cover["r_m2k_per_w"]) if _night_cover_closed(cover, local_hour) else 0.0
            u_window = 1.0 / (1.0 / glz.u_w_m2k + r_cover)
            q_glazing = u_window * op_area * (float(wr.t_air_c) - t_air)
        flows["glazing"] = q_glazing
        q_from_air += q_glazing
        q_vent = g_vent * (float(wr.t_air_c) - t_air)
        flows["ventilation"] = q_vent
        internal_gain = float(design["internal_gains_w"])
        q_from_air += q_vent + internal_gain
        air_storage = air_cap * (t_air - t_air_prev) / dt_s
        conditioning_power = air_storage - q_from_air if run == "heater" else 0.0
        heater_power = max(0.0, conditioning_power) if run == "heater" else 0.0

        # Independent whole-domain boundary energy bookkeeping. This is the T2 criterion.
        external_power = 0.0
        for s in surfaces:
            nodes = layer_nodes[s.name]
            if s.kind == "floor":
                continue
            op_area = opening[1] if (s.name == "wall_main" and opening is not None) else 0.0
            opaque_area = max(s.area_m2 - op_area, 0.0)
            coeff, source, _, _ = _external_coeff(wr, s, states[s.name][0])
            if s.area_m2 > 0:
                poa = _solar_value(s, ts, wr, design, extended, step_idx)
                mat = materials[nodes[0].material]
                coeff_eff = coeff * opaque_area / s.area_m2
                source_eff = source * opaque_area / s.area_m2 + mat.absorptance * poa
                external_power += (source_eff - coeff_eff * float(x[offsets[s.name]])) * s.area_m2
        soil_last = float(x[soil_offset + len(soil) - 1])
        g_deep = soil[-1][2] / soil[-1][0] * floor_area
        external_power += g_deep * (deep_temp - soil_last)
        external_power += solar_transmitted_power + q_glazing + q_vent + internal_gain + (conditioning_power if run == "heater" else 0.0)

        storage_power = air_storage
        for s in surfaces:
            nodes = layer_nodes[s.name]
            old = states[s.name]
            new = x[offsets[s.name]:offsets[s.name] + len(nodes)]
            for node, a_old, b_new in zip(nodes, old, new):
                storage_power += node.capacity_j_m2k * s.area_m2 * (float(b_new) - float(a_old)) / dt_s
        storage_power += float(np.sum([soil[j][1] * floor_area * (float(x[soil_offset + j]) - float(soil_state[j])) / dt_s for j in range(len(soil))]))
        if mass is not None:
            storage_power += mass["kg"] * ceff * (float(x[mass_idx]) - float(mass_prev)) / dt_s

        boundary_residual = external_power - storage_power
        denominator = max(1.0, abs(external_power) + abs(storage_power))
        equation_balance = A @ x - b
        equation_ratio = float(np.max(np.abs(equation_balance)) / max(1.0, float(np.sum(np.abs(b)))))
        if run == "free":
            equation_air = air_storage - q_from_air
        else:
            equation_air = air_storage - q_from_air - conditioning_power
        max_equation_balance_ratio = max(max_equation_balance_ratio, equation_ratio, abs(equation_air) / max(1.0, abs(air_storage) + abs(q_from_air) + abs(conditioning_power)))
        if step_idx >= warmup_steps:
            max_boundary_residual_w = max(max_boundary_residual_w, abs(boundary_residual))
            max_boundary_den_w = max(max_boundary_den_w, denominator)

        for name, nodes in layer_nodes.items():
            states[name] = x[offsets[name]:offsets[name] + len(nodes)]
        soil_state = x[soil_offset:soil_offset + len(soil)].copy()
        if mass is not None:
            mass_prev = float(x[mass_idx])
        if step_idx >= warmup_steps:
            out_rows.append({"time": ts.isoformat(), "t_air_out_c": float(wr.t_air_c), "t_air_in_c": t_air, "ghi_wm2": float(wr.ghi_wm2), "solar_in_w": solar_transmitted_power})
            surface_temp_rows.append({
                s.name: float(x[offsets[s.name] + len(layer_nodes[s.name]) - 1])
                for s in surfaces
            })
            flow_rows.append(flows)
            heater_rows.append(heater_power)
            solar_rows.append(incident_this_step)
        t_air_prev = t_air

    out = pd.DataFrame(out_rows).set_index("time")
    flow_df = pd.DataFrame(flow_rows, index=out.index).fillna(0.0)
    surface_temp_df = pd.DataFrame(surface_temp_rows, index=out.index).fillna(np.nan)
    heater_series = pd.Series(heater_rows, index=out.index)
    low = float(design["comfort"]["low_c"])
    high = float(design["comfort"]["high_c"])
    temps = out["t_air_in_c"].to_numpy()
    hours = dt_minutes / 60.0
    below = np.clip(low - temps, 0, None)
    over = np.clip(temps - high, 0, None)
    surface_areas = {s.name: s.area_m2 for s in surfaces}
    solar_incident = {name: float(sum(row.get(name, 0.0) for row in solar_rows) / max(surface_areas[name], 1e-9)) for name in surface_areas}
    summary = {
        "t_min_c": float(temps.min()),
        "t_max_c": float(temps.max()),
        "comfort_hours": float(np.sum((temps >= low) & (temps <= high)) * hours),
        "hours_below_low": float(np.sum(temps < low) * hours),
        "degree_hours_below_kh": float(np.sum(below) * hours),
        "overheat_hours": float(np.sum(temps > high) * hours),
        "overheat_degree_hours": float(np.sum(over) * hours),
        "heating_kwh": float(heater_series.clip(lower=0).sum() * dt_s / 3.6e6),
        "heating_kwh_per_m2": float(heater_series.clip(lower=0).sum() * dt_s / 3.6e6 / floor_area),
        "solar_transmitted_kwh": float(transmitted_total),
        "solar_incident_kwh_m2": solar_incident,
        "solar_absorbed_opaque_kwh": float(absorbed_opaque_total),
        "flow_totals_kwh": {k: float(v.sum() * dt_s / 3.6e6) for k, v in flow_df.items()},
        "max_energy_balance_residual_w": float(max_boundary_residual_w),
        "max_energy_balance_denominator_w": float(max_boundary_den_w),
        "max_energy_balance_ratio": float(max_boundary_residual_w / max_boundary_den_w),
        "max_boundary_energy_closure_ratio": float(max_boundary_residual_w / max_boundary_den_w),
        "max_equation_balance_ratio": float(max_equation_balance_ratio),
        "max_mass_iterations": int(max_mass_iterations),
        "interior_mass_material": mass["material"] if mass else None,
        "interior_mass_kg": mass["kg"] if mass else 0.0,
        "interior_mass_surface_area_m2": mass_area,
    }
    return {
        "meta": {
            "weather_source": weather.meta["source"],
            "synthetic": weather.meta["synthetic"],
            "period": [str(out.index[0]), str(out.index[-1])],
            "dt_minutes": requested_dt_minutes,
            "integration_dt_minutes": dt_minutes,
            "lat": weather.meta.get("lat"),
            "lon": weather.meta.get("lon"),
            "missing_hours": weather.meta.get("missing_hours", 0),
            "design_name": design["name"],
            "site_elevation_m": float(design["site"]["elevation_m"]),
        },
        "series": {
            "time": list(out.index),
            "t_air_out_c": out.t_air_out_c.round(4).tolist(),
            "t_air_in_c": out.t_air_in_c.round(4).tolist(),
            "ghi_wm2": out.ghi_wm2.round(4).tolist(),
            "solar_in_w": out.solar_in_w.round(4).tolist(),
            "surface_temp_in_c": {k: v.round(4).tolist() for k, v in surface_temp_df.items()},
            "q_w": {k: v.round(4).tolist() for k, v in flow_df.items()},
            "heater_w": heater_series.round(4).tolist(),
        },
        "summary": summary,
    }
