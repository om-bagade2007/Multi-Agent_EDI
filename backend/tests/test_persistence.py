"""SQLite repository round-trip verification."""
from app.db.repository import Repository


def test_repository_persists_run_incidents_and_dispatches() -> None:
    repository = Repository()
    run_id = repository.save({"seed": 5, "incidents": [{"id": "I1", "type": "medical"}], "decisions": [{"id": "D1", "incident_id": "I1", "unit_id": "A1"}], "metrics": {"avg_response_s": 30}})
    saved = {row["id"]: row for row in repository.list_runs()}
    assert saved[run_id]["seed"] == 5
    assert saved[run_id]["metrics"]["avg_response_s"] == 30
