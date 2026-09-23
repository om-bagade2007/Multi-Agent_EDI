"""Persisted runs and event/decision records."""
from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RunRow(Base):
    """Simulation run summary."""
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    seed: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[float] = mapped_column(Float)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")


class IncidentRow(Base):
    """Incident snapshot storage."""
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    data_json: Mapped[str] = mapped_column(Text)


class DispatchRow(Base):
    """Explainable dispatch record."""
    __tablename__ = "dispatches"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    incident_id: Mapped[str] = mapped_column(String)
    data_json: Mapped[str] = mapped_column(Text)


class UnitEventRow(Base):
    """Unit lifecycle event record."""
    __tablename__ = "unit_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    data_json: Mapped[str] = mapped_column(Text)


class MetricSnapshotRow(Base):
    """Time series metric snapshot."""
    __tablename__ = "metric_snapshots"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    sim_time: Mapped[float] = mapped_column(Float)
    data_json: Mapped[str] = mapped_column(Text)
