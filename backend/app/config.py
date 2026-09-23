"""Application environment settings."""
from pathlib import Path

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
    simulation_mode: str = "pune"
    pune_data_dir: Path = REPO_ROOT / "data" / "pune"
