from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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


settings = Settings()
