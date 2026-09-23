"""Validated domain models shared by the simulation, API and persistence layers."""
from enum import StrEnum

from pydantic import BaseModel, Field


class AgentKind(StrEnum):
    """Responder or hospital agent type."""
    ambulance = "ambulance"
    fire = "fire"
    police = "police"
    hospital = "hospital"


class IncidentType(StrEnum):
    """Supported emergency types."""
    accident = "accident"
    fire = "fire"
    medical = "medical"


class IncidentStatus(StrEnum):
    """Lifecycle state for an incident."""
    pending = "pending"
    dispatched = "dispatched"
    on_scene = "on_scene"
    resolved = "resolved"


class UnitStatus(StrEnum):
    """Lifecycle state for a response unit."""
    idle = "idle"
    en_route = "en_route"
    on_scene = "on_scene"
    transporting = "transporting"
    at_hospital = "at_hospital"
    returning = "returning"


class LatLon(BaseModel):
    """Geographic coordinate in decimal degrees."""
    lat: float = Field(allow_inf_nan=False)
    lon: float = Field(allow_inf_nan=False)


class Incident(BaseModel):
    """Emergency demand and its response requirements."""
    id: str
    type: IncidentType
    severity: int = Field(ge=1, le=5)
    location: LatLon
    created_at: float
    requires: set[AgentKind] = Field(default_factory=set)
    injuries: bool = False
    status: IncidentStatus = IncidentStatus.pending


class Unit(BaseModel):
    """A movable responder and its assignment state."""
    id: str
    kind: AgentKind
    station_id: str
    location: LatLon
    status: UnitStatus = UnitStatus.idle
    assigned_incident_id: str | None = None


class Station(BaseModel):
    """A unit's home base."""
    id: str
    kind: AgentKind
    location: LatLon


class Hospital(BaseModel):
    """Hospital bed and intensive care capacity."""
    id: str
    name: str | None = None
    location: LatLon
    beds_total: int
    beds_free: int
    icu_total: int
    icu_free: int


class Candidate(BaseModel):
    """A ranked unit candidate for a dispatch decision."""
    unit_id: str
    eta_s: float
    distance_m: float


class DispatchDecision(BaseModel):
    """Explainable selection and alternatives for one response unit."""
    id: str
    incident_id: str
    unit_id: str
    eta_s: float
    chosen_reason: str
    candidates: list[Candidate]
    strategy: str = "nearest"
    sim_time: float
