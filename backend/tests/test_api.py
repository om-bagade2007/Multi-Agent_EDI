"""REST and WebSocket integration tests with the in-memory bus."""
from fastapi.testclient import TestClient

from app.main import app


def test_api_live_run_controls_and_snapshot() -> None:
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/scenario").json()["grid_size"] == 8
    response = client.post("/runs", json={"seed": 9, "duration_s": 3600, "incident_rate": 5})
    assert response.status_code == 200
    run_id = response.json()["id"]
    assert client.post(f"/runs/{run_id}/pause").status_code == 200
    assert client.post(f"/runs/{run_id}/resume").status_code == 200
    with client.websocket_connect(f"/ws/runs/{run_id}") as socket:
        message = socket.receive_json()
        assert message["type"] == "snapshot"
        assert "units" in message and "traffic" in message
    assert client.post(f"/runs/{run_id}/stop").status_code == 200
