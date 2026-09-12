from __future__ import annotations

from sqlalchemy.orm import Session

from app.adapters.ollama_adapter import list_installed_ollama_models, normalize_ollama_base_url
from app.config.model_registry import list_models, resolve_model_info
from app.core.config import settings
from app.models.domain import Experiment, ProviderKey

AUTO_MODEL_ID = "auto"
AUTO_EXPAND_LIMIT = 8


def configured_model_ids(db: Session, project_id: str) -> list[str]:
    keys = db.query(ProviderKey).filter(ProviderKey.project_id == project_id).all()
    available: list[str] = []
    seen: set[str] = set()
    for key in keys:
        if key.provider_name == "ollama":
            base_url = normalize_ollama_base_url(key.ollama_base_url or settings.ollama_base_url, settings.ollama_base_url)
            tags, _error = list_installed_ollama_models(base_url)
            for tag in tags:
                if tag not in seen:
                    available.append(tag)
                    seen.add(tag)
            continue
        if not key.encrypted_api_key:
            continue
        for model in list_models(provider=key.provider_name, include_disabled=False):
            if model.id not in seen:
                available.append(model.id)
                seen.add(model.id)
    return available


def pick_auto_model(db: Session, project_id: str) -> str:
    candidates = configured_model_ids(db, project_id)
    if not candidates:
        raise ValueError("Auto mode requires at least one configured provider with available models")

    experiment = (
        db.query(Experiment)
        .filter(Experiment.project_id == project_id, Experiment.status == "completed")
        .order_by(Experiment.created_at.desc())
        .first()
    )
    if experiment and (experiment.results_json or {}).get("rows"):
        rows = [row for row in (experiment.results_json.get("rows") or []) if not row.get("error")]
        options: list[dict] = []
        for model_id in candidates:
            group = [row for row in rows if row.get("model_id") == model_id]
            if not group:
                continue
            options.append(
                {
                    "model_id": model_id,
                    "prompt_id": group[0].get("prompt_id"),
                    "quality_score": sum((row.get("quality_score") or 0.0) for row in group) / len(group),
                    "cost_usd": sum((row.get("cost_usd") or 0.0) for row in group) / len(group),
                    "latency_ms": sum((row.get("latency_ms") or 0.0) for row in group) / len(group),
                    "structured_output": True,
                }
            )
        if options:
            from app.services.phase1 import score_recommendations

            ranked, _, top, _ = score_recommendations(options, {"goal": "highest_quality"})
            if ranked:
                return str(top["model_id"])

    preferred = ["gpt-4o-mini", "gpt-4o", "llama3.2", "llama3.2:latest", "gemini-2.0-flash", "mistral", "mistral:latest"]
    for model_id in preferred:
        if model_id in candidates:
            return model_id
        prefix_match = next((item for item in candidates if item.split(":", 1)[0] == model_id), None)
        if prefix_match:
            return prefix_match
    return candidates[0]


def expand_model_ids(db: Session, project_id: str, model_ids: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    wants_auto = any(model_id.lower() == AUTO_MODEL_ID for model_id in model_ids)
    explicit = [model_id for model_id in model_ids if model_id.lower() != AUTO_MODEL_ID]

    if wants_auto:
        available = configured_model_ids(db, project_id)
        if not available:
            raise ValueError("Auto mode requires at least one configured provider with available models")
        # Auto runs the user's available models so recommendations have something to compare.
        source = explicit + available[:AUTO_EXPAND_LIMIT] if explicit else available[:AUTO_EXPAND_LIMIT]
    else:
        source = explicit

    for resolved in source:
        info = resolve_model_info(resolved)
        if info is None:
            ollama_configured = (
                db.query(ProviderKey)
                .filter(ProviderKey.project_id == project_id, ProviderKey.provider_name == "ollama")
                .one_or_none()
            )
            if ollama_configured is None:
                raise ValueError(f"Model '{resolved}' is not enabled")
        if resolved not in seen:
            expanded.append(resolved)
            seen.add(resolved)
    if not expanded:
        raise ValueError("At least one model is required")
    return expanded
