"""Small persistence repository for completed and active runs."""
import json
from uuid import uuid4

from app.db.session import Base, SessionLocal, engine
from app.db.tables import DispatchRow, IncidentRow, MetricSnapshotRow, RunRow, UnitEventRow


class Repository:
    """Persist and query episode records through SQLAlchemy."""
    def __init__(self) -> None:
        Base.metadata.create_all(engine)

    def save(self, result: dict[str, object], run_id: str | None = None) -> str:
        """Write an episode result and its incidents and decisions."""
        key = run_id or str(uuid4())
        with SessionLocal.begin() as session:
            session.merge(RunRow(id=key, seed=int(result["seed"]), status="completed", created_at=0.0, metrics_json=json.dumps(result.get("metrics", {}))))
            for incident in result.get("incidents", []):
                if isinstance(incident, dict):
                    session.merge(IncidentRow(id=f"{key}:{incident['id']}", run_id=key, data_json=json.dumps(incident)))
            for decision in result.get("decisions", []):
                if isinstance(decision, dict):
                    session.merge(DispatchRow(id=f"{key}:{decision['id']}", run_id=key, incident_id=str(decision["incident_id"]), data_json=json.dumps(decision)))
            for index, event in enumerate(result.get("unit_events", [])):
                if isinstance(event, dict):
                    session.merge(UnitEventRow(id=f"{key}:unit:{index}", run_id=key, data_json=json.dumps(event)))
            for snapshot in result.get("metric_snapshots", []):
                if isinstance(snapshot, dict):
                    sim_time = float(snapshot.get("sim_time", 0))
                    session.merge(MetricSnapshotRow(id=f"{key}:metric:{sim_time:.0f}", run_id=key, sim_time=sim_time, data_json=json.dumps(snapshot)))
        return key

    def list_runs(self) -> list[dict[str, object]]:
        """Return saved run summaries."""
        from app.db.tables import RunRow
        with SessionLocal() as session:
            return [{"id": row.id, "seed": row.seed, "status": row.status, "metrics": json.loads(row.metrics_json)} for row in session.query(RunRow).all()]
