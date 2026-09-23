"""Application environment settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration with offline-safe defaults."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    sim_backend: str = "grid"
    bus: str = "memory"
    database_url: str = "sqlite:///./urban_sim.db"
    redis_url: str = "redis://localhost:6379/0"
    sumo_home: str = ""
    dispatch_strategy: str = "nearest"
