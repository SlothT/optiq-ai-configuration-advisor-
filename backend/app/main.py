from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from sqlalchemy import text

from app.api.advice import router as advice_router
from app.api.auth import router as auth_router
from app.api.experiments import router as experiments_router
from app.api.feedback import router as feedback_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.prompts import router as prompts_router
from app.api.providers import router as providers_router
from app.api.recommendations import router as recommendations_router
from app.core.config import settings
from app.core.database import engine

app = FastAPI(
    title=settings.app_name,
    description="AI Configuration Advisor API",
    version="0.2.0",
)

allowed_origins = {
    settings.frontend_url.rstrip("/"),
    *(origin.rstrip("/") for origin in settings.cors_origins),
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(origin for origin in allowed_origins if origin),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(advice_router)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(providers_router)
app.include_router(prompts_router)
app.include_router(experiments_router)
app.include_router(feedback_router)
app.include_router(recommendations_router)


@app.get("/health")
def root_health() -> dict:
    return {"status": "ok", "service": "optiq-api"}


@app.get("/health/ready")
def readiness() -> dict:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT version_num FROM alembic_version"))
        if settings.job_backend == "rq":
            with Redis.from_url(settings.redis_url, socket_connect_timeout=3, socket_timeout=3) as client:
                client.ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Application dependencies are not ready.") from exc
    return {"status": "ready"}
