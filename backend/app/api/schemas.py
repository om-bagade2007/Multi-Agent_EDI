"""API request schemas."""
from pydantic import BaseModel, ConfigDict, Field


class RunRequest(BaseModel):
    """Parameters for a seeded episode."""
    strategy: str | None = None
    seed: int = 1
    incident_rate: float = Field(default=2/3, ge=0)
    duration_s: float = Field(default=3600, gt=0)
    speed: float = Field(default=1, gt=0)


class PunePoint(BaseModel):
    """Finite real coordinate constrained to the central Pune bbox."""
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=18.47, le=18.58, allow_inf_nan=False)
    lon: float = Field(ge=73.79, le=73.93, allow_inf_nan=False)


class PuneCoordinatePayload(BaseModel):
    """Validate all moving Pune entities and route vertices before websocket send."""
    coordinates: list[PunePoint]
