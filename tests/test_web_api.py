from fastapi.testclient import TestClient

from vajra.api import app


def test_weather_info_is_fast_metadata_path():
    client = TestClient(app)
    response = client.get("/api/weather-info")
    assert response.status_code == 200
    body = response.json()
    assert body["rows"] > 0
    assert "source" in body["meta"]


def test_default_uses_selected_window_and_not_full_year():
    client = TestClient(app)
    response = client.get("/api/default?days=14")
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["meta"]["dt_minutes"] == 60
    assert len(body["result"]["series"]["time"]) == 14 * 24


def test_invalid_weather_period_is_rejected():
    client = TestClient(app)
    response = client.get("/api/default?days=21")
    assert response.status_code == 400
