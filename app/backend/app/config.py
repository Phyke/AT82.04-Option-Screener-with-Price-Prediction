from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    MODEL_PATH: Path = Path("models/price_model.pkl")
    FEATURE_SCALER_PATH: Path = Path("models/feature_scaler.pkl")
    DEMO_SNAPSHOT_PATH: Path = Path("data/demo_snapshot.pkl")
    OPTION_CHAIN_TTL_SECONDS: int = 300
    DAILY_HISTORY_TTL_SECONDS: int = 86_400
    YF_CONCURRENCY: int = 8
    LOG_LEVEL: str = "INFO"
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PREFIX: str = "options-app"
    CORS_ORIGINS: Annotated[list[str], NoDecode] = []
    CORS_ORIGIN_REGEX: str = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


settings = Settings()
