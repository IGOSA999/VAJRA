from __future__ import annotations
import time
from fastapi.testclient import TestClient
from vajra.api import app, default_design


def measure(client, method, path, **kwargs):
    wall0 = time.perf_counter()
    cpu0 = time.process_time()
    response = getattr(client, method)(path, **kwargs)
    return path, response.status_code, time.perf_counter() - wall0, time.process_time() - cpu0


if __name__ == "__main__":
    with TestClient(app) as client:
        design = default_design()
        checks = [
            measure(client, "get", "/api/health"),
            measure(client, "get", "/api/weather-info?source=bundled"),
            measure(client, "get", "/api/materials"),
            measure(client, "get", "/api/default?days=14&coldest=true&source=bundled"),
            measure(client, "post", "/api/run?days=14&coldest=true&source=bundled", json=design),
            measure(client, "post", "/api/compare?days=14&coldest=true&source=bundled", json=design),
            measure(client, "post", "/api/compare-materials?days=14&coldest=true&source=bundled", json=design),
            measure(client, "get", "/api/default?days=365&coldest=false&source=bundled"),
        ]
        for path, status, wall, cpu in checks:
            print(f"{path} status={status} wall_s={wall:.4f} cpu_s={cpu:.4f}")
