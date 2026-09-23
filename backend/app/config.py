"""Application environment settings."""
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration with offline-safe defaults."""
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")
    sim_backend: str = "grid"
    bus: str = "memory"
    database_url: str = "sqlite:///./urban_sim.db"
    redis_url: str = "redis://localhost:6379/0"
    sumo_home: str = ""
    dispatch_strategy: str = "nearest"
    simulation_mode: Literal["pune", "gridsim"] = "pune"
    pune_data_dir: Path = REPO_ROOT / "data" / "pune"

    @field_validator("pune_data_dir", mode="before")
    @classmethod
    def resolve_pune_data_dir(cls, value: object) -> Path:
        """Resolve configured relative paths against the repository root."""
        path = Path(value)
        return path if path.is_absolute() else REPO_ROOT / path
