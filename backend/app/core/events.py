"""Typed event envelope used by all agents."""
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class Event(BaseModel):
    """Serializable event with simulation and wall-clock timestamps."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    sim_time: float
    wall_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str
    payload: dict[str, object]


def make_event(event_type: str, sim_time: float, source: str, **payload: object) -> Event:
    """Build an event envelope from a type and payload."""
    return Event(type=event_type, sim_time=sim_time, source=source, payload=payload)
