import json
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    APP_NAME: str = "3D Cinema Platform API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    SECRET_KEY: str = "insecure_dev_secret_key_must_be_changed_in_production"
    ALLOWED_HOSTS: Union[str, List[str]] = ["*"]
    CORS_ORIGINS: Union[str, List[str]] = ["http://localhost:3000", "http://localhost:5173", "https://*.vercel.app"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://cinema_user:cinema_password@localhost:5432/cinema_platform"
    DATABASE_SYNC_URL: str = "postgresql://cinema_user:cinema_password@localhost:5432/cinema_platform"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Business Invariants
    SEAT_LOCK_EXPIRATION_SECONDS: int = 600

    @field_validator("CORS_ORIGINS", "ALLOWED_HOSTS", mode="after")
    @classmethod
    def assemble_list(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def assemble_database_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


settings = Settings()
