from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-insecure-secret-replace-in-every-real-deployment"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://ptcl:ptcl@localhost:5432/ptcl"

    jwt_secret: str = DEV_JWT_SECRET
    jwt_expires_in: int = 3600

    upload_dir: Path = Path("./var/uploads")
    export_dir: Path = Path("./var/exports")
    max_upload_bytes: int = 25 * 1024 * 1024

    deployment_profile: str = "prototype"

    hosted_llm_base_url: str = ""
    hosted_llm_api_key: str = ""
    hosted_llm_model: str = "Qwen/Qwen2.5-7B-Instruct"
    llm_max_repair_retries: int = 1

    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_task_always_eager: bool = True

    cors_allow_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://localhost:5175",
    ]

    @model_validator(mode="after")
    def _refuse_the_dev_secret_outside_dev(self) -> Settings:
        if self.app_env != "dev" and self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError(
                f"JWT_SECRET is still the development default while APP_ENV={self.app_env}. "
                "Set a real secret of at least 32 bytes."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
