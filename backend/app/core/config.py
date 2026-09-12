from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_files() -> tuple[str, ...]:
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

    database_url: str = "postgresql+psycopg2://optiq:optiq_dev_password@localhost:5432/optiq"
    redis_url: str = "redis://localhost:6379/0"
    mlflow_tracking_uri: str = "http://localhost:5000"

    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    fernet_key: str = ""

    frontend_url: str = "http://localhost:3000"
    google_client_id: str = ""
    ollama_base_url: str = "http://localhost:11434"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    resend_api_key: str = ""


settings = Settings()
