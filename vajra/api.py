from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .materials import load_glazing, load_materials
from .solver import simulate, validate_design
from .weather import load_weather_csv, load_nasa_csv, synthetic_leh, select_window
from .optimise import compare_designs, compare_materials
from .report import design_sheet_html
from .ansys_export import export_ansys_case

ROOT = Path(__file__).resolve().parents[1]
MATERIALS = ROOT / "data" / "materials.csv"
GLAZING = ROOT / "data" / "glazing.csv"
WEATHER_DIR = ROOT / "data" / "weather"
WEB = ROOT / "web"
ACTIVE_WEATHER: Path | None = None

app = FastAPI(title="VAJRA thermal shelter model")
app.mount("/static", StaticFiles(directory=WEB), name="static")


def default_design() -> dict:
    return {
        "name": "Leh reference shelter",
        "site": {"lat": 34.1526, "lon": 77.5771, "elevation_m": 3500},
        "geometry": {
            "length_m": 4.0, "width_m": 3.0, "wall_height_m": 2.4,
            "roof": {"type": "mono_pitch", "pitch_deg": 15, "high_side": "N"},
            "azimuth_deg": 180,
        },
        "constructions": {
            "wall": [{"material": "stone_masonry", "mm": 300}],
            "roof": [{"material": "mineral_wool", "mm": 100}, {"material": "timber", "mm": 25}],
            "floor": [{"material": "concrete_dense", "mm": 100}],
            "ground": {"soil_depth_m": 2.0},
        },
        "openings": [{"facade": "main", "width_m": 1.8, "height_m": 1.2, "glazing": "double_clear",
                       "night_cover": {"r_m2k_per_w": 0.8, "from_hour": 17, "to_hour": 9}}],
        "air": {"infiltration_ach": 0.5, "vent_ach": 0.0, "vent_hours": [11, 15]},
        "internal_gains_w": 0,
        "solar_split": {"floor_and_mass": 0.7},
        "comfort": {"low_c": 15, "high_c": 28},
        "setpoint_c": 15,
        "ground_reflectance": 0.2,
        "interior_mass": None,
    }


def current_weather(days: int | None = None):
    if ACTIVE_WEATHER is not None:
        weather = load_weather_csv(ACTIVE_WEATHER)
    else:
        candidates = sorted(WEATHER_DIR.glob("leh_*_hourly.csv"))
        if candidates:
            weather = load_nasa_csv(candidates[-1], 34.1526, 77.5771, 3500.0)
        else:
            weather = synthetic_leh(14)
    return select_window(weather, days) if days is not None else weather


def _coldest_fortnight(weather, days: int = 14):
    """Return the coldest contiguous window by rolling mean temperature."""
    if days <= 0:
        raise ValueError("Weather window must be positive")
    frame = weather.frame.sort_index()
    span = days * 24
    if len(frame) <= span + 24:
        return weather
    rolling = frame["t_air_c"].rolling(span).mean()
    valid = rolling.notna()
    if not valid.any():
        return weather
    end_pos = int(np.flatnonzero(valid.to_numpy())[np.argmin(rolling.to_numpy()[valid.to_numpy()])])
    part = frame.iloc[max(0, end_pos - span + 1):end_pos + 1]
    meta = dict(weather.meta)
    meta["window_note"] = f"coldest {days} days of the file, {part.index[0].date()} to {part.index[-1].date()}"
    return type(weather)(part, meta)


def requested_days(days: int) -> int:
    allowed = {14, 30, 365}
    if days not in allowed:
        raise HTTPException(status_code=400, detail="Weather period must be 14, 30 or 365 days")
    return days


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/materials")
def materials():
    mats = load_materials(MATERIALS)
    glz = load_glazing(GLAZING)
    return {
        "materials": {k: vars(v) for k, v in mats.items()},
        "glazing": {k: vars(v) for k, v in glz.items()},
    }


@app.get("/api/weather-info")
def weather_info():
    weather = current_weather()
    return {"meta": weather.meta, "rows": len(weather.frame), "start": str(weather.start), "end": str(weather.end)}


@app.get("/api/default")
def default_case(days: int = 14):
    days = requested_days(days)
    design = default_design()
    weather = current_weather(days)
    result = simulate(design, weather, MATERIALS, GLAZING, dt_minutes=60, run="free")
    heater = simulate(design, weather, MATERIALS, GLAZING, dt_minutes=60, run="heater")
    result["summary"]["heating_kwh"] = heater["summary"]["heating_kwh"]
    result["summary"]["heating_kwh_per_m2"] = heater["summary"]["heating_kwh_per_m2"]
    result["series"]["heater_w"] = heater["series"]["heater_w"]
    return {"design": design, "result": result}


@app.post("/api/run")
def run_case(design: dict, days: int = 14):
    try:
        days = requested_days(days)
        weather = current_weather(days)
        result = simulate(design, weather, MATERIALS, GLAZING, dt_minutes=60, run="free")
        heater = simulate(design, weather, MATERIALS, GLAZING, dt_minutes=60, run="heater")
        result["summary"]["heating_kwh"] = heater["summary"]["heating_kwh"]
        result["summary"]["heating_kwh_per_m2"] = heater["summary"]["heating_kwh_per_m2"]
        result["series"]["heater_w"] = heater["series"]["heater_w"]
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/compare")
def compare_case(design: dict, days: int = 14):
    try:
        days = requested_days(days)
        weather = current_weather(days)
        return {"rows": compare_designs(design, weather, MATERIALS, GLAZING, candidate_count=6)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/compare-materials")
def compare_material_case(design: dict, days: int = 14):
    try:
        days = requested_days(days)
        weather = current_weather(days)
        return {"rows": compare_materials(design, weather, MATERIALS, GLAZING)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/upload-weather")
async def upload_weather(file: UploadFile = File(...)):
    global ACTIVE_WEATHER
    try:
        target = ROOT / "data" / "weather" / Path(file.filename or "weather.csv").name
        target.write_bytes(await file.read())
        wf = load_weather_csv(target)
        ACTIVE_WEATHER = target
        return {"source": wf.meta, "rows": len(wf.frame), "start": str(wf.start), "end": str(wf.end)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/design-sheet", response_class=HTMLResponse)
def make_design_sheet(payload: dict):
    return HTMLResponse(design_sheet_html(payload["design"], payload["result"]))


@app.post("/api/ansys")
def ansys(payload: dict, days: int = 14):
    try:
        days = requested_days(days)
        design = payload.get("design")
        if not isinstance(design, dict):
            raise ValueError("ANSYS export needs a design object")
        validate_design(design)
        out = export_ansys_case(design, current_weather(days), MATERIALS, GLAZING)
        return {"files": [str(x.relative_to(ROOT)) for x in out]}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
