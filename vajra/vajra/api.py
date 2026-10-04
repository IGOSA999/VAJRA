from __future__ import annotations

import copy
import json
import logging
import math
import multiprocessing as mp
import threading
import time
import uuid
from concurrent.futures import ProcessPoolExecutor
from io import BytesIO
from pathlib import Path
import zipfile

import pandas as pd

from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .materials import load_glazing, load_materials
from .solver import simulate, validate_design
from .weather import load_weather_csv, load_nasa_csv, synthetic_leh, select_window, WeatherFrame
from .optimise import compare_designs, compare_materials, generate_candidates, _row_from_runs
from .report import design_sheet_html, section_svg
from .ansys_export import export_ansys_case

ROOT = Path(__file__).resolve().parents[1]
MATERIALS = ROOT / "data" / "materials.csv"
GLAZING = ROOT / "data" / "glazing.csv"
WEATHER_DIR = ROOT / "data" / "weather"
WEB = ROOT / "web"
ACTIVE_WEATHER: Path | None = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
LOG = logging.getLogger("vajra")

EXECUTOR: ProcessPoolExecutor | None = None
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def _worker_pair(design, weather, materials_path, glazing_path):
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    free = simulate(design, weather, materials_path, glazing_path, dt_minutes=60, run="free")
    heater = simulate(design, weather, materials_path, glazing_path, dt_minutes=60, run="heater")
    free["summary"]["heating_kwh"] = heater["summary"]["heating_kwh"]
    free["summary"]["heating_kwh_per_m2"] = heater["summary"]["heating_kwh_per_m2"]
    free["series"]["heater_w"] = heater["series"]["heater_w"]
    return {"result": free, "server_elapsed_wall_s": time.perf_counter()-started_wall, "server_cpu_s": time.process_time()-started_cpu}


def _worker_design_row(design, weather, materials_path, glazing_path):
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    free = simulate(design, weather, materials_path, glazing_path, dt_minutes=60, run="free")
    heater = simulate(design, weather, materials_path, glazing_path, dt_minutes=60, run="heater")
    return {"row": _row_from_runs(design, free, heater), "server_elapsed_wall_s": time.perf_counter()-started_wall, "server_cpu_s": time.process_time()-started_cpu}


def default_design() -> dict:
    return {
        "name": "Leh reference shelter",
        "site": {"lat": 34.1526, "lon": 77.5771, "elevation_m": 3500},
        "geometry": {"length_m": 4.0, "width_m": 3.0, "wall_height_m": 2.4, "roof": {"type": "mono_pitch", "pitch_deg": 15, "high_side": "N"}, "azimuth_deg": 180},
        "constructions": {"wall": [{"material": "stone_masonry", "mm": 300}], "roof": [{"material": "mineral_wool", "mm": 100}, {"material": "timber", "mm": 25}], "floor": [{"material": "concrete_dense", "mm": 100}], "ground": {"soil_depth_m": 2.0}},
        "openings": [{"facade": "main", "width_m": 1.8, "height_m": 1.2, "glazing": "double_clear", "night_cover": {"r_m2k_per_w": 0.8, "from_hour": 17, "to_hour": 9}}],
        "air": {"infiltration_ach": 0.5, "vent_ach": 0.0, "vent_hours": [11, 15]},
        "internal_gains_w": 0, "solar_split": {"floor_and_mass": 0.7}, "comfort": {"low_c": 15, "high_c": 28}, "setpoint_c": 15, "ground_reflectance": 0.2, "interior_mass": None,
    }


def _load_bundled_weather() -> WeatherFrame:
    candidates = sorted(WEATHER_DIR.glob("leh_*_hourly.csv"))
    if candidates:
        return load_nasa_csv(candidates[-1], 34.1526, 77.5771, 3500.0)
    return synthetic_leh(14)


def _load_active_weather(source: str = "active") -> WeatherFrame:
    if source == "bundled":
        return _load_bundled_weather()
    if source == "upload":
        if ACTIVE_WEATHER is None:
            raise ValueError("No uploaded weather file is active. Choose a CSV and click Use uploaded weather.")
        return load_weather_csv(ACTIVE_WEATHER)
    if ACTIVE_WEATHER is not None:
        return load_weather_csv(ACTIVE_WEATHER)
    return _load_bundled_weather()


def _coldest_window(weather: WeatherFrame, days: int) -> WeatherFrame:
    if days <= 0:
        raise ValueError("Weather window must be positive")
    frame = weather.frame.sort_index()
    span = days * 24
    if len(frame) <= span:
        return weather
    daily = frame["t_air_c"].resample("1D").mean()
    rolling = daily.rolling(days).mean()
    end_day = rolling.idxmin()
    start = end_day - pd.Timedelta(days=days-1)
    idx = frame.index
    part = frame.loc[(idx >= start) & (idx < end_day + pd.Timedelta(days=1))].copy()
    meta = dict(weather.meta)
    meta["window_note"] = f"coldest {days} days of the file, {part.index[0].date()} to {part.index[-1].date()}"
    return WeatherFrame(part, meta)


def current_weather(days: int | None = None, coldest: bool = False, source: str = "active"):
    weather = _load_active_weather(source)
    if days is None:
        return weather
    return _coldest_window(weather, days) if coldest else select_window(weather, days)


def _coldest_fortnight(weather: WeatherFrame, days: int = 14) -> WeatherFrame:
    return _coldest_window(weather, days)


def requested_days(days: int) -> int:
    if days not in {14, 30, 365}:
        raise HTTPException(status_code=400, detail="Weather period must be 14, 30 or 365 days")
    return days


app = FastAPI(title="VAJRA thermal shelter model")
app.mount("/static", StaticFiles(directory=WEB), name="static")


def _ensure_executor():
    global EXECUTOR
    if EXECUTOR is None:
        EXECUTOR = ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context("spawn"))
        LOG.info("VAJRA worker process pool ready")
    return EXECUTOR


@app.on_event("startup")
def startup():
    _ensure_executor()


@app.on_event("shutdown")
def shutdown():
    global EXECUTOR
    if EXECUTOR is not None:
        EXECUTOR.shutdown(wait=False, cancel_futures=True)
        EXECUTOR = None


@app.middleware("http")
async def request_metrics(request: Request, call_next):
    wall = time.perf_counter(); cpu = time.process_time(); response = None
    try:
        response = await call_next(request)
        return response
    finally:
        LOG.info("request path=%s wall_s=%.4f cpu_s=%.4f status=%s", request.url.path, time.perf_counter()-wall, time.process_time()-cpu, getattr(response, "status_code", 500))


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = str(exc.detail or "").strip() or f"The server returned an error (HTTP {exc.status_code})."
    return JSONResponse(status_code=exc.status_code, content={"detail": detail, "type": "HTTPException"})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": str(exc), "type": "RequestValidationError"})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    LOG.error("unhandled exception on %s", request.url.path, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}", "type": type(exc).__name__})


@app.get("/")
def index(): return FileResponse(WEB / "index.html")

@app.get("/favicon.ico")
def favicon(): return FileResponse(WEB / "favicon.svg", media_type="image/svg+xml")

@app.get("/api/health")
def health(): return {"ok": True}

@app.get("/api/materials")
def materials():
    mats, glz = load_materials(MATERIALS), load_glazing(GLAZING)
    return {"materials": {k: vars(v) for k,v in mats.items()}, "glazing": {k: vars(v) for k,v in glz.items()}}

@app.get("/api/weather-info")
def weather_info(source: str = "active"):
    weather = current_weather(source=source)
    return {"meta": weather.meta, "rows": len(weather.frame), "start": str(weather.start), "end": str(weather.end)}

@app.get("/api/default")
def default_case(days: int=14, coldest: bool=False, source: str="active"):
    days = requested_days(days); design = default_design(); weather = current_weather(days, coldest, source)
    return {"design": design, "result": _worker_pair(design, weather, MATERIALS, GLAZING)["result"]}

@app.post("/api/run")
def run_case(design: dict, days: int=14, coldest: bool=False, source: str="active"):
    days = requested_days(days); validate_design(design)
    return _worker_pair(design, current_weather(days, coldest, source), MATERIALS, GLAZING)["result"]

@app.post("/api/compare")
def compare_case(design: dict, days: int=14, coldest: bool=False, source: str="active"):
    days = requested_days(days); validate_design(design)
    return {"rows": compare_designs(design, current_weather(days, coldest, source), MATERIALS, GLAZING, candidate_count=6)}

@app.post("/api/compare-materials")
def compare_material_case(design: dict, days: int=14, coldest: bool=False, source: str="active"):
    days = requested_days(days); validate_design(design)
    return {"rows": compare_materials(design, current_weather(days, coldest, source), MATERIALS, GLAZING)}

@app.post("/api/use-bundled-weather")
def use_bundled_weather():
    global ACTIVE_WEATHER
    ACTIVE_WEATHER = None
    weather = _load_bundled_weather()
    return {"source": weather.meta}

@app.post("/api/upload-weather")
async def upload_weather(file: UploadFile = File(...)):
    global ACTIVE_WEATHER
    try:
        target = ROOT / "data" / "weather" / Path(file.filename or "weather.csv").name
        target.write_bytes(await file.read())
        wf = load_weather_csv(target); ACTIVE_WEATHER = target
        return {"source": wf.meta, "rows": len(wf.frame), "start": str(wf.start), "end": str(wf.end)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/section")
def section(payload: dict):
    design = payload.get("design")
    if not isinstance(design, dict): raise HTTPException(status_code=400, detail="Section needs a design object")
    validate_design(design)
    meta = payload.get("weather_meta") or {}
    return Response(content=section_svg(design, meta, payload.get("period")), media_type="image/svg+xml")

@app.post("/api/design-sheet", response_class=HTMLResponse)
def make_design_sheet(payload: dict):
    return HTMLResponse(design_sheet_html(payload["design"], payload["result"]))

@app.get("/api/ansys-validation")
def ansys_validation():
    path = ROOT / "data" / "ansys_validation.json"
    if not path.exists(): raise HTTPException(status_code=404, detail="ANSYS validation record is not available")
    return json.loads(path.read_text(encoding="utf-8"))

@app.post("/api/ansys-package")
def ansys_package(payload: dict, days: int=14, coldest: bool=False, source: str="active"):
    design = payload.get("design")
    if not isinstance(design, dict): raise HTTPException(status_code=400, detail="ANSYS export needs a design object")
    validate_design(design)
    files = export_ansys_case(design, current_weather(requested_days(days), coldest, source), MATERIALS, GLAZING)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files: archive.write(path, arcname=path.name)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="VAJRA_ANSYS_Level_A.zip"'})

@app.post("/api/ansys")
def ansys(payload: dict, days: int=14, coldest: bool=False, source: str="active"):
    design = payload.get("design")
    if not isinstance(design, dict): raise HTTPException(status_code=400, detail="ANSYS export needs a design object")
    validate_design(design)
    out = export_ansys_case(design, current_weather(requested_days(days), coldest, source), MATERIALS, GLAZING)
    return {"files": [str(x.relative_to(ROOT)) for x in out]}


def _job_record(kind, total):
    return {"status":"running","progress":0,"total":total,"rows":[],"kind":kind,"result":None,"error":None,"elapsed_wall_s":None,"elapsed_cpu_s":None,"futures":[],"started_at":time.perf_counter(),"period":None}


def _watch_job(job_id: str):
    with JOBS_LOCK:
        job = JOBS[job_id]
        futures = list(job["futures"])
    started = job["started_at"]
    try:
        for i, future in enumerate(futures):
            result = future.result()
            with JOBS_LOCK:
                if job["status"] == "cancelled":
                    continue
                if job["kind"] in {"run", "default"}:
                    job["result"] = result
                else:
                    job["rows"].append(result["row"])
                job["progress"] = i + 1
                job["elapsed_wall_s"] = time.perf_counter() - started
                job["elapsed_cpu_s"] = float(result.get("server_cpu_s", 0.0))
        with JOBS_LOCK:
            if job["status"] not in {"cancelled", "failed"}:
                job["status"] = "done"
                job["elapsed_wall_s"] = time.perf_counter() - started
    except Exception as exc:
        with JOBS_LOCK:
            if job["status"] != "cancelled":
                job["status"] = "failed"
                job["error"] = f"{type(exc).__name__}: {exc}"
                job["elapsed_wall_s"] = time.perf_counter() - started
        for future in futures:
            if not future.done(): future.cancel()


def _start_job(kind: str, design: dict | None, days: int, coldest: bool=False, source: str="active") -> str:
    executor = _ensure_executor()
    weather = current_weather(days, coldest, source)
    job_id = uuid.uuid4().hex
    if kind in {"run","default"}:
        work = copy.deepcopy(design or default_design())
        futures = [executor.submit(_worker_pair, work, weather, MATERIALS, GLAZING)]
    else:
        base = copy.deepcopy(design or default_design())
        if kind == "compare":
            designs = [base] + generate_candidates(base, 6, seed=20261003)
        else:
            designs = []
            for material in ["stone_masonry","concrete_dense","fired_clay_brick","rammed_earth","adobe","timber"]:
                d = copy.deepcopy(base)
                d["name"] = f"material_{material}"
                d["constructions"]["wall"] = [{"material":"mineral_wool","mm":100},{"material":material,"mm":300}]
                designs.append(d)
        futures = [executor.submit(_worker_design_row, d, weather, MATERIALS, GLAZING) for d in designs]
    with JOBS_LOCK:
        rec = _job_record(kind, len(futures)); rec["futures"] = futures; rec["period"] = [str(weather.start), str(weather.end)]; JOBS[job_id] = rec
    threading.Thread(target=_watch_job, args=(job_id,), daemon=True).start()
    return job_id

@app.post("/api/jobs/default")
def job_default(days: int=14, coldest: bool=True, source: str="active"):
    days = requested_days(days); job_id = _start_job("default", default_design(), days, coldest, source)
    return {"job_id":job_id,"kind":"default","design":default_design()}

@app.post("/api/jobs/run")
def job_run(design: dict, days: int=14, coldest: bool=True, source: str="active"):
    days = requested_days(days); validate_design(design); return {"job_id":_start_job("run",design,days,coldest,source),"kind":"run"}

@app.post("/api/jobs/compare")
def job_compare(design: dict, days: int=14, coldest: bool=True, source: str="active"):
    days = requested_days(days); validate_design(design); return {"job_id":_start_job("compare",design,days,coldest,source),"kind":"compare"}

@app.post("/api/jobs/materials")
def job_materials(design: dict, days: int=14, coldest: bool=True, source: str="active"):
    days = requested_days(days); validate_design(design); return {"job_id":_start_job("materials",design,days,coldest,source),"kind":"materials"}

@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with JOBS_LOCK:
        if job_id not in JOBS: raise HTTPException(status_code=404, detail="The server restarted and this computation was lost. Press Run again.")
        job = JOBS[job_id]
        payload = {k:job[k] for k in ["status","progress","total","rows","kind","result","error","elapsed_wall_s","elapsed_cpu_s","period"]}
        if job["status"] == "running": payload["elapsed_wall_s"] = time.perf_counter() - job["started_at"]
        return payload

@app.post("/api/jobs/{job_id}/cancel")
def job_cancel(job_id: str):
    with JOBS_LOCK:
        if job_id not in JOBS: raise HTTPException(status_code=404, detail="The server restarted and this computation was lost. Press Run again.")
        job = JOBS[job_id]
        if job["status"] == "done": return {"status":"done"}
        job["status"] = "cancelled"
        for future in job["futures"]: future.cancel()
    return {"status":"cancelled"}
