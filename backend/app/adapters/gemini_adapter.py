from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import BaseAdapter, GenerateResult
from app.adapters.retries import with_retries


class GeminiAdapter(BaseAdapter):
    provider_name = "google"

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
            contents = [{"role": "user", "parts": [{"text": prompt}]}]
            payload_in: dict[str, Any] = {
                "contents": contents,
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
            }
            if system:
                payload_in["systemInstruction"] = {"parts": [{"text": system}]}
            response = self._client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent",
                params={"key": self.api_key},
                json=payload_in,
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            candidates = payload.get("candidates") or []
            parts = (((candidates[0] or {}).get("content") or {}).get("parts") or []) if candidates else []
            text = "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))
            usage = payload.get("usageMetadata") or {}
            return GenerateResult(
                text=text,
                raw=payload,
                input_tokens=usage.get("promptTokenCount"),
                output_tokens=usage.get("candidatesTokenCount"),
            )

        return with_retries(_call)

    def health_check(self) -> bool:
        return bool(self.api_key)
