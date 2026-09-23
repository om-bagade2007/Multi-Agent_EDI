"""API request schemas."""
from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    """Parameters for a seeded episode."""
    strategy: str = "nearest"
    seed: int = 1
    incident_rate: float = Field(default=2/3, ge=0)
    duration_s: float = Field(default=3600, gt=0)
    speed: float = Field(default=1, gt=0)
