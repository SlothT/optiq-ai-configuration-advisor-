from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.advice import router as advice_router
from app.api.auth import router as auth_router
from app.api.experiments import router as experiments_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.prompts import router as prompts_router
from app.api.providers import router as providers_router
from app.api.recommendations import router as recommendations_router
from app.core.config import settings

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
app.include_router(recommendations_router)


@app.get("/health")
def root_health() -> dict:
    return {"status": "ok", "service": "optiq-api"}
