from fastapi import APIRouter

from app.config.model_registry import list_models, list_providers

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/health")
def health_check() -> dict:
    return {"status": "ok", "service": "optiq-api"}


@router.get("/models")
def get_models() -> dict:
    models = list_models()
    return {
        "providers": list_providers(),
        "models": [
            {
                "id": model.id,
                "provider": model.provider,
                "display_name": model.display_name,
                "default_temperature": model.default_temperature,
                "max_tokens": model.max_tokens,
                "pricing": (
                    {
                        "input_per_1m": model.pricing.input_per_1m,
                        "output_per_1m": model.pricing.output_per_1m,
                    }
                    if model.pricing
                    else None
                ),
            }
            for model in models
        ],
        "count": len(models),
    }
