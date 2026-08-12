from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config.model_registry import list_models, provider_requires_api_key
from app.core.crypto import encrypt_text
from app.core.deps import db_session, get_current_user, get_project_for_user
from app.models.domain import Project, ProviderKey, User
from app.schemas.domain import ProviderUpsertRequest, ProviderView
from app.services.phase1 import list_project_provider_views

router = APIRouter(prefix="/api/v1/projects/{project_id}/providers", tags=["providers"])


@router.get("", response_model=list[ProviderView])
def list_project_providers(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> list[dict]:
    get_project_for_user(project_id, current_user, db)
    return list_project_provider_views(db, project_id)


@router.post("", response_model=ProviderView)
def upsert_provider(
    project_id: str,
    request: ProviderUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> dict:
    get_project_for_user(project_id, current_user, db)
    provider_cfg = next((item for item in list_project_provider_views(db, project_id) if item["provider_name"] == request.provider_name), None)
    if not provider_cfg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not supported")

    if request.provider_name != "ollama" and provider_requires_api_key(request.provider_name) and not request.api_key:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="API key is required for this provider")

    existing = (
        db.query(ProviderKey)
        .filter(ProviderKey.project_id == project_id, ProviderKey.provider_name == request.provider_name)
        .one_or_none()
    )
    if not existing:
        existing = ProviderKey(project_id=project_id, provider_name=request.provider_name)
        db.add(existing)

    existing.encrypted_api_key = encrypt_text(request.api_key) if request.api_key else None
    existing.ollama_base_url = request.ollama_base_url.strip() if request.ollama_base_url else None
    db.commit()
    db.refresh(existing)
    return {
        "provider_name": existing.provider_name,
        "configured": True,
        "has_api_key": bool(existing.encrypted_api_key),
        "ollama_base_url": existing.ollama_base_url,
        "available_models": [
            {
                "id": model.id,
                "display_name": model.display_name,
                "default_temperature": model.default_temperature,
                "max_tokens": model.max_tokens,
                "pricing": None
                if not model.pricing
                else {"input_per_1m": model.pricing.input_per_1m, "output_per_1m": model.pricing.output_per_1m},
            }
            for model in list_models(provider=request.provider_name, include_disabled=False)
        ],
    }


@router.delete("/{provider_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(
    project_id: str,
    provider_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> Response:
    get_project_for_user(project_id, current_user, db)
    provider = (
        db.query(ProviderKey)
        .filter(ProviderKey.project_id == project_id, ProviderKey.provider_name == provider_name)
        .one_or_none()
    )
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not configured")
    db.delete(provider)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
