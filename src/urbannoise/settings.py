"""Runtime settings. Secrets come from the environment, never from source defaults in production."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UNLAB_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/urbannoise.db"
    jwt_secret: str = "dev-only-not-for-production-use-32b"
    jwt_exp_minutes: int = 720
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    auto_seed: bool = True
    data_dir: str = "./data"
    phase2_dir: str = "experiments/results/phase2"
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]
