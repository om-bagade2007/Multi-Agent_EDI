from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    health = TestClient(app).get("/health").json()
    assert health["status"] == "ok"
    assert health["mode"] == "pune"
    assert int(health["nodes"]) >= 1500
