"""REST and WebSocket integration tests with the in-memory bus."""
from math import isfinite

from fastapi.testclient import TestClient

from app.main import app


def test_api_live_run_controls_and_snapshot() -> None:
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    scenario = client.get("/scenario").json()
    assert scenario["grid_size"] == 8
    assert scenario["mode"] == "gridsim" and scenario["dispatch_strategy"] == "nearest"
    response = client.post("/runs", json={"seed": 1, "duration_s": 3600, "incident_rate": 5})
    assert response.status_code == 200
    run_id = response.json()["id"]
    assert client.post(f"/runs/{run_id}/pause").status_code == 200
    assert client.post(f"/runs/{run_id}/resume").status_code == 200
    with client.websocket_connect(f"/ws/runs/{run_id}") as socket:
        message = socket.receive_json()
        assert message["type"] == "snapshot"
        assert "units" in message and "traffic" in message
        assert "stations" in message and "hospitals" in message and "agents" in message
        network = message["road_network"]
        assert len(network["nodes"]) == 64 and len(network["edges"]) == 112
        node_ids = {node["id"] for node in network["nodes"]}
        assert all(isfinite(node[axis]) for node in network["nodes"] for axis in ("x", "y"))
        assert all(edge["from_node"] in node_ids and edge["to_node"] in node_ids for edge in network["edges"])
        assert all(isfinite(edge[axis]) for edge in network["edges"] for axis in ("x1", "y1", "x2", "y2"))
        assert "utilization" in message["metrics"] and "response_by_type" in message["metrics"]
    assert client.post(f"/runs/{run_id}/stop").status_code == 200
