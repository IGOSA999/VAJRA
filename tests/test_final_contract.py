from pathlib import Path
from vajra.api import default_design
from vajra.report import section_svg

ROOT = Path(__file__).resolve().parents[1]

def test_no_favicon_gap_and_ansys_record():
    assert (ROOT / "web" / "favicon.svg").is_file()
    assert (ROOT / "data" / "ansys_validation.json").is_file()

def test_section_scale_uses_real_dimensions():
    d=default_design(); svg=section_svg(d, {"provider":"NASA POWER","year":2024}, ["2024-01-01","2024-01-14"])
    assert "1 m" in svg and "300 mm" in svg
    assert svg.count("mineral") == 0 or "Mineral wool" in svg

def test_solver_summary_dynamic_metrics_exist():
    # Contract-level check: these names must remain part of the public result vocabulary.
    from vajra.solver import simulate
    from vajra.weather import synthetic_leh
    from vajra.api import MATERIALS, GLAZING
    d=default_design()
    result=simulate(d, synthetic_leh(2), MATERIALS, GLAZING, 60, "free")
    for key in ("hours_above_zero","mean_delta_c","solar_incident_kwh_m2","solar_transmitted_kwh","solar_absorbed_opaque_kwh"):
        assert key in result["summary"]


def test_no_large_embedded_series_or_result_cache():
    import re
    forbidden_names = {"default_result", "cached_run", "demo_output", "precomputed"}
    for base in (ROOT / "web", ROOT / "vajra"):
        for path in base.rglob("*"):
            if not path.is_file() or "vendor" in path.parts or "fonts" in path.parts:
                continue
            assert path.name.lower() not in forbidden_names
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in re.finditer(r"\[[^\[\]]*(?:-?\d+\.?\d*,){50}", text):
                raise AssertionError(f"Embedded numeric series detected in {path}")


def test_heat_flow_sign_is_documented():
    src = (ROOT / "vajra" / "solver.py").read_text(encoding="utf-8")
    assert "q = h_in * opaque * (inner_t - t_air)" in src
    assert "Positive means heat entering the room" in (ROOT / "web" / "app.js").read_text(encoding="utf-8")


def test_background_job_starts_immediately_and_health_stays_responsive():
    import time
    from fastapi.testclient import TestClient
    from vajra.api import app, default_design
    with TestClient(app) as client:
        started = time.perf_counter()
        response = client.post("/api/jobs/run?days=14&coldest=true&source=bundled", json=default_design())
        submit_wall = time.perf_counter() - started
        assert response.status_code == 200
        assert submit_wall < 1.0
        assert client.get("/api/health").status_code == 200
