from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.adapters.base import BaseAdapter, GenerateResult
from app.adapters.retries import with_retries


def normalize_ollama_base_url(url: str | None, fallback: str = "http://localhost:11434") -> str:
    raw = (url or fallback).strip()
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return fallback.rstrip("/")
    path = (parsed.path or "").rstrip("/")
    for suffix in ("/v1/chat/completions", "/api/chat", "/v1"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            break
    cleaned = f"{parsed.scheme}://{parsed.netloc}{path}".rstrip("/")
    return cleaned or fallback.rstrip("/")


def list_installed_ollama_models(base_url: str) -> tuple[list[str], str | None]:
    url = normalize_ollama_base_url(base_url)
    try:
        response = httpx.get(f"{url}/api/tags", timeout=8.0)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        names = []
        seen: set[str] = set()
        for item in payload.get("models") or []:
            name = str(item.get("name") or item.get("model") or "").strip()
            if name and name not in seen and "embed" not in name.lower():
                names.append(name)
                seen.add(name)
        return names, None
    except Exception as exc:
        return [], f"Could not list Ollama models at {url}: {exc}"


class OllamaAdapter(BaseAdapter):
    provider_name = "ollama"

    def __init__(self, base_url: str) -> None:
        self.base_url = normalize_ollama_base_url(base_url)
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
        endpoint = f"{self.base_url}/api/chat"

        def _call() -> GenerateResult:
            response = self._client.post(
                endpoint,
                json={
                    "model": model_id,
                    "messages": [
                        {"role": "system", "content": system or "Follow the user's instructions exactly."},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                },
            )
            if response.status_code == 404:
                raise ValueError(
                    f"Ollama could not find model '{model_id}' at {endpoint}. "
                    f"Pull it with `ollama pull {model_id}` and use a model from the available list."
                )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            message = payload.get("message") or {}
            text = str(message.get("content") or payload.get("response") or "")
            return GenerateResult(
                text=text,
                raw=payload,
                input_tokens=payload.get("prompt_eval_count"),
                output_tokens=payload.get("eval_count"),
            )

        return with_retries(_call)

    def health_check(self) -> bool:
        try:
            response = self._client.get(f"{self.base_url}/api/tags", timeout=8.0)
            return response.status_code == 200
        except Exception:
            return False

    def embed(self, texts: list[str], model_id: str | None = None) -> list[list[float]] | None:
        vectors: list[list[float]] = []
        embed_model = model_id or "nomic-embed-text"
        try:
            for text in texts:
                response = self._client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": embed_model, "prompt": text},
                    timeout=60.0,
                )
                response.raise_for_status()
                payload = response.json()
                vectors.append(list(payload.get("embedding") or []))
            return vectors if all(vectors) else None
        except Exception:
            return None
