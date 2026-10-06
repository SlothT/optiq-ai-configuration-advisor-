import os
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_files() -> tuple[str, ...]:
    if os.environ.get("OPTIQ_ENV_FILE"):
        return (os.environ["OPTIQ_ENV_FILE"],)
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / ".env",  # /app/.env in Docker; backend/.env locally
        here.parents[3] / ".env" if len(here.parents) > 3 else None,  # repo root locally
    ]
    found = [str(path) for path in candidates if path is not None and path.is_file()]
    return tuple(found) or (".env",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_files(), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Optiq"
    debug: bool = False
    job_backend: Literal["rq", "thread"] = "rq"
    mail_backend: Literal["smtp", "file"] = "smtp"
    mail_directory: Path = Path(".local/mail")

    database_url: str
    redis_url: str = ""
    mlflow_tracking_uri: str = ""

    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    fernet_key: str = ""

    frontend_url: str = ""
    cors_origins: list[str] = []
    google_client_id: str = ""
    ollama_base_url: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    resend_api_key: str = ""

    @model_validator(mode="after")
    def validate_development_backends(self) -> "Settings":
        if not self.debug and (self.mail_backend == "file" or self.job_backend == "thread"):
            raise ValueError("MAIL_BACKEND=file and JOB_BACKEND=thread require DEBUG=true; use SMTP and RQ when deployed")
        return self


settings = Settings()
