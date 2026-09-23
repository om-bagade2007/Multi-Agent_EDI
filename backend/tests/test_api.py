"""REST and WebSocket integration tests with the in-memory bus."""
from math import isfinite
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app


def test_api_live_run_controls_and_snapshot() -> None:
    client = TestClient(app)
    health = client.get("/health").json()
    assert health["status"] == "ok" and health["mode"] == "pune"
    scenario = client.get("/scenario").json()
    assert scenario["mode"] == "pune" and scenario["dispatch_strategy"] == "nearest"
    assert scenario["speeds"] == [1, 5, 10, 30]
    base_network = client.get("/scenario/network").json()
    assert base_network["mode"] == "pune"
    assert len(base_network["roads"]["features"]) > 1500
    facilities = client.get("/scenario/facilities").json()
    assert sum(facility["kind"] == "hospital" for facility in facilities) >= 3
    response = client.post("/runs", json={"seed": 1, "duration_s": 3600, "incident_rate": 5})
    assert response.status_code == 200
    run_id = response.json()["id"]
    assert client.post(f"/runs/{run_id}/pause").status_code == 200
    assert client.post(f"/runs/{run_id}/resume").status_code == 200
    with client.websocket_connect(f"/ws/runs/{run_id}") as socket:
        message = socket.receive_json()
        assert message["type"] == "snapshot"
        assert "units" in message and "traffic" in message and "routes" in message
        assert "stations" in message and "hospitals" in message and "agents" in message
        points = [item["location"] for group in (message["units"], message["incidents"], message["stations"], message["hospitals"]) for item in group]
        points.extend(point for route in message["routes"] for point in route["polyline"])
        assert all(isfinite(point[axis]) for point in points for axis in ("lat", "lon"))
        assert all(18.47 <= point["lat"] <= 18.58 and 73.79 <= point["lon"] <= 73.93 for point in points)
        assert "utilization" in message["metrics"] and "response_by_type" in message["metrics"]
    assert client.post(f"/runs/{run_id}/stop").status_code == 200


def test_missing_pune_data_is_reported_without_grid_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(routes._settings, "pune_data_dir", tmp_path)
    routes._load_pune_network.cache_clear()
    client = TestClient(app)
    assert client.get("/scenario").json()["mode"] == "pune"
    assert client.get("/scenario/network").status_code == 503
    assert client.get("/scenario/facilities").status_code == 503
    health = client.get("/health").json()
    assert health["status"] == "error" and "make pune-data" in health["detail"]
