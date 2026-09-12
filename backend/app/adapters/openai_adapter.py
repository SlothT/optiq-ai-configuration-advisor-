from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import BaseAdapter, GenerateResult
from app.adapters.retries import with_retries


class OpenAIAdapter(BaseAdapter):
    provider_name = "openai"

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
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": model_id,
                    "messages": [
                        {"role": "system", "content": system or "Follow the user's instructions exactly."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            text = str(payload["choices"][0]["message"]["content"] or "")
            usage = payload.get("usage") or {}
            return GenerateResult(
                text=text,
                raw=payload,
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            )

        return with_retries(_call)

    def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            response = self._client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15.0,
            )
            return response.status_code < 500
        except Exception:
            return False

    def embed(self, texts: list[str], model_id: str | None = None) -> list[list[float]] | None:
        if not texts:
            return []

        def _call() -> list[list[float]]:
            response = self._client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": model_id or "text-embedding-3-small", "input": texts},
                timeout=60.0,
            )
            response.raise_for_status()
            payload = response.json()
            data = sorted(payload.get("data") or [], key=lambda item: item.get("index", 0))
            return [list(item["embedding"]) for item in data]

        try:
            return with_retries(_call)
        except Exception:
            return None
