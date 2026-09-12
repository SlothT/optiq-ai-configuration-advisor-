from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import BaseAdapter, GenerateResult
from app.adapters.retries import with_retries


class AnthropicAdapter(BaseAdapter):
    provider_name = "anthropic"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._client = httpx.Client(timeout=120.0)

    def generate(
        self,
        *,
        model_id: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        system: str | None = None,
    ) -> GenerateResult:
        def _call() -> GenerateResult:
            response = self._client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model_id,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system or "Follow the user's instructions exactly.",
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            blocks = payload.get("content") or []
            text = "".join(str(block.get("text") or "") for block in blocks if isinstance(block, dict))
            usage = payload.get("usage") or {}
            return GenerateResult(
                text=text,
                raw=payload,
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
            )

        return with_retries(_call)

    def health_check(self) -> bool:
        return bool(self.api_key)
