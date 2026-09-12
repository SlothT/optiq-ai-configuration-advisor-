from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).parent / "models.yaml"


@dataclass(frozen=True)
class ModelPricing:
    input_per_1m: float
    output_per_1m: float


@dataclass(frozen=True)
class ModelInfo:
    id: str
    provider: str
    adapter: str
    display_name: str
    pricing: ModelPricing | None
    default_temperature: float
    max_tokens: int
    enabled: bool


def _parse_pricing(raw: dict[str, Any] | None) -> ModelPricing | None:
    if not raw:
        return None
    return ModelPricing(
        input_per_1m=float(raw["input_per_1m"]),
        output_per_1m=float(raw["output_per_1m"]),
    )


@lru_cache
def load_registry() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def list_providers() -> list[str]:
    registry = load_registry()
    return list(registry.get("providers", {}).keys())


def list_models(*, provider: str | None = None, include_disabled: bool = False) -> list[ModelInfo]:
    registry = load_registry()
    models: list[ModelInfo] = []

    for provider_name, provider_cfg in registry.get("providers", {}).items():
        if provider and provider_name != provider:
            continue

        provider_enabled = bool(provider_cfg.get("enabled", True))
        adapter = provider_cfg.get("adapter", provider_name)

        for model_id, model_cfg in provider_cfg.get("models", {}).items():
            model_enabled = bool(model_cfg.get("enabled", provider_enabled))
            if not include_disabled and not model_enabled:
                continue

            models.append(
                ModelInfo(
                    id=model_id,
                    provider=provider_name,
                    adapter=adapter,
                    display_name=str(model_cfg.get("display_name", model_id)),
                    pricing=_parse_pricing(model_cfg.get("pricing")),
                    default_temperature=float(model_cfg.get("default_temperature", 0.7)),
                    max_tokens=int(model_cfg.get("max_tokens", 4096)),
                    enabled=model_enabled,
                )
            )

    return models


def get_model(model_id: str) -> ModelInfo | None:
    for model in list_models(include_disabled=True):
        if model.id == model_id:
            return model if model.enabled else None
    return None


def resolve_model_info(model_id: str) -> ModelInfo | None:
    found = get_model(model_id)
    if found:
        return found
    short = model_id.split(":", 1)[0]
    if short == model_id:
        return None
    found = get_model(short)
    if not found:
        return None
    return ModelInfo(
        id=model_id,
        provider=found.provider,
        adapter=found.adapter,
        display_name=found.display_name,
        pricing=found.pricing,
        default_temperature=found.default_temperature,
        max_tokens=found.max_tokens,
        enabled=found.enabled,
    )


def synthetic_ollama_model(model_id: str) -> ModelInfo:
    resolved = resolve_model_info(model_id)
    if resolved and resolved.provider == "ollama":
        return resolved
    return ModelInfo(
        id=model_id,
        provider="ollama",
        adapter="ollama",
        display_name=model_id,
        pricing=None,
        default_temperature=0.7,
        max_tokens=4096,
        enabled=True,
    )


def model_is_local(model_id: str) -> bool:
    model = resolve_model_info(model_id)
    if model is None:
        return False
    return model.pricing is None


def get_provider_config(provider_name: str) -> dict[str, Any] | None:
    registry = load_registry()
    return registry.get("providers", {}).get(provider_name)


def provider_requires_api_key(provider_name: str) -> bool:
    provider_cfg = get_provider_config(provider_name)
    if not provider_cfg:
        return False
    return bool(provider_cfg.get("requires_api_key", False))
