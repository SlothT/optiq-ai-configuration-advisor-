from __future__ import annotations

from app.adapters.anthropic_adapter import AnthropicAdapter
from app.adapters.base import BaseAdapter, ProviderResolution
from app.adapters.gemini_adapter import GeminiAdapter
from app.adapters.ollama_adapter import OllamaAdapter, normalize_ollama_base_url
from app.adapters.openai_adapter import OpenAIAdapter
from app.config.model_registry import resolve_model_info, synthetic_ollama_model
from app.core.config import settings
from app.core.crypto import decrypt_text
from app.models.domain import ProviderKey


class AdapterFactory:
    @staticmethod
    def from_resolution(resolution: ProviderResolution) -> BaseAdapter:
        provider = resolution.provider_name
        key = resolution.provider_key
        if provider == "openai":
            api_key = decrypt_text(key.encrypted_api_key or "") if key and key.encrypted_api_key else ""
            if not api_key:
                raise ValueError(f"OpenAI is not configured for model '{resolution.model_id}'")
            return OpenAIAdapter(api_key)
        if provider == "ollama":
            base_url = (key.ollama_base_url if key and key.ollama_base_url else None) or settings.ollama_base_url
            return OllamaAdapter(normalize_ollama_base_url(base_url, settings.ollama_base_url))
        if provider == "anthropic":
            api_key = decrypt_text(key.encrypted_api_key or "") if key and key.encrypted_api_key else ""
            if not api_key:
                raise ValueError(f"Anthropic is not configured for model '{resolution.model_id}'")
            return AnthropicAdapter(api_key)
        if provider in {"google", "gemini"}:
            api_key = decrypt_text(key.encrypted_api_key or "") if key and key.encrypted_api_key else ""
            if not api_key:
                raise ValueError(f"Google Gemini is not configured for model '{resolution.model_id}'")
            return GeminiAdapter(api_key)
        raise ValueError(f"Unsupported provider '{provider}'")

    @staticmethod
    def embedding_adapter(resolution: ProviderResolution) -> BaseAdapter | None:
        try:
            return AdapterFactory.from_resolution(resolution)
        except ValueError:
            return None


def resolve_provider(db, project_id: str, model_id: str) -> ProviderResolution:
    model = resolve_model_info(model_id)
    if not model:
        ollama_key = (
            db.query(ProviderKey)
            .filter(ProviderKey.project_id == project_id, ProviderKey.provider_name == "ollama")
            .one_or_none()
        )
        if ollama_key is None:
            raise ValueError(f"Model '{model_id}' is not enabled or does not exist")
        model = synthetic_ollama_model(model_id)
    provider_key = (
        db.query(ProviderKey)
        .filter(ProviderKey.project_id == project_id, ProviderKey.provider_name == model.provider)
        .one_or_none()
    )
    return ProviderResolution(
        provider_name=model.provider,
        model_id=model.id,
        provider_key=provider_key,
        model_config=model,
    )
