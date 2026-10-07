import os
from email.utils import parseaddr
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import field_validator, model_validator
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
    app_env: Literal["development", "test", "production"] = "development"
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
    brevo_api_key: str = ""
    embedded_worker: bool = False

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg2://" + value[len(prefix):]
        return value

    @model_validator(mode="after")
    def validate_development_backends(self) -> "Settings":
        if not self.debug and (self.mail_backend == "file" or self.job_backend == "thread"):
            raise ValueError("MAIL_BACKEND=file and JOB_BACKEND=thread require DEBUG=true; use SMTP and RQ when deployed")
        if self.app_env == "production":
            if self.debug or self.job_backend != "rq" or self.mail_backend != "smtp":
                raise ValueError("Production requires DEBUG=false, JOB_BACKEND=rq, and MAIL_BACKEND=smtp")
            if not self.database_url.startswith("postgresql") or not self.redis_url:
                raise ValueError("Production requires Postgres DATABASE_URL and REDIS_URL")
            if len(self.jwt_secret) < 32 or self.jwt_secret in {"dev-secret-change-in-production", "__JWT_SECRET__"}:
                raise ValueError("Production requires a generated JWT_SECRET of at least 32 characters")
            try:
                Fernet(self.fernet_key.encode())
            except (ValueError, TypeError) as exc:
                raise ValueError("Production requires a valid FERNET_KEY") from exc
            for origin in [self.frontend_url, *self.cors_origins]:
                parsed = urlsplit(origin)
                if parsed.scheme != "https" or not parsed.hostname or parsed.hostname in {"localhost", "127.0.0.1"} or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username:
                    raise ValueError("Production requires HTTPS FRONTEND_URL and CORS_ORIGINS without paths")
            sender = parseaddr(self.smtp_from)[1]
            if "@" not in sender or sender.endswith(".local") or not (self.resend_api_key or self.brevo_api_key or self.smtp_host):
                raise ValueError("Production requires a real SMTP_FROM and Brevo/Resend API key or SMTP host")
        return self


settings = Settings()
