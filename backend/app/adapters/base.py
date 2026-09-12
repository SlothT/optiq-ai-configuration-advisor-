from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.models.domain import ProviderKey


@dataclass(frozen=True)
class ProviderResolution:
    provider_name: str
    model_id: str
    provider_key: ProviderKey | None
    model_config: Any


@dataclass
class GenerateResult:
    text: str
    raw: dict[str, Any] = field(default_factory=dict)
    input_tokens: int | None = None
    output_tokens: int | None = None


class BaseAdapter(ABC):
    provider_name: str

    @abstractmethod
    def generate(
        self,
        *,
        model_id: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        system: str | None = None,
    ) -> GenerateResult:
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        raise NotImplementedError

    def get_pricing(self, model_id: str) -> dict[str, float] | None:
        from app.config.model_registry import resolve_model_info

        model = resolve_model_info(model_id)
        if not model or not model.pricing:
            return None
        return {
            "input_per_1m": model.pricing.input_per_1m,
            "output_per_1m": model.pricing.output_per_1m,
        }

    def estimate_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        from app.services.phase1 import estimate_cost

        return estimate_cost(model_id, input_tokens, output_tokens)

    def embed(self, texts: list[str], model_id: str | None = None) -> list[list[float]] | None:
        return None
