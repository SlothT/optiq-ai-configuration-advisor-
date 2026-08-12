from __future__ import annotations

import csv
import json
import math
import tempfile
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import mlflow
import tiktoken
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config.model_registry import get_model, get_provider_config, list_models
from app.core.config import settings
from app.core.crypto import decrypt_text
from app.models.domain import Experiment, Prompt, Project, ProviderKey, Recommendation, User

TASK_KEYWORDS = {
    "summarization": ["summary", "summarize", "condense"],
    "qa": ["question", "answer", "qa"],
    "sql_generation": ["sql", "query", "database"],
    "classification": ["classify", "label", "category"],
    "open_ended": [],
}


@dataclass(frozen=True)
class ProviderResolution:
    provider_name: str
    model_id: str
    provider_key: ProviderKey | None
    model_config: Any


@dataclass(frozen=True)
class PromptAnalysis:
    quality_score: float
    strengths: list[str]
    weaknesses: list[str]
    suggested_improvements: list[str]
    analysis_json: dict[str, Any]
    estimated_tokens: int
    estimated_cost_usd: float
    judge_model: str | None


@dataclass(frozen=True)
class ExperimentRunResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]



def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def estimate_tokens(text: str, model_id: str | None = None) -> int:
    try:
        encoding = tiktoken.encoding_for_model(model_id or "gpt-4o-mini")
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    model = get_model(model_id)
    if not model or not model.pricing:
        return 0.0
    input_cost = (input_tokens / 1_000_000) * model.pricing.input_per_1m
    output_cost = (output_tokens / 1_000_000) * model.pricing.output_per_1m
    return round(input_cost + output_cost, 6)


def _prompt_family_version(db: Session, project_id: str, source_prompt_id: str | None) -> int:
    if source_prompt_id:
        source = db.query(Prompt).filter(Prompt.id == source_prompt_id, Prompt.project_id == project_id).one_or_none()
        if not source:
            raise ValueError("Prompt not found for re-analysis")
        return source.version + 1
    latest = (
        db.query(func.max(Prompt.version))
        .filter(Prompt.project_id == project_id)
        .scalar()
    )
    return int(latest or 0) + 1


def analyze_prompt_text(prompt_text: str, task_type: str) -> tuple[float, list[str], list[str], list[str]]:
    normalized = normalize_whitespace(prompt_text)
    strengths: list[str] = []
    weaknesses: list[str] = []
    suggestions: list[str] = []
    score = 100.0

    word_count = len(normalized.split())
    if word_count >= 75:
        strengths.append("Enough detail for a robust model response")
    elif word_count < 25:
        weaknesses.append("Prompt is very short and may be underspecified")
        suggestions.append("Add task context, constraints, and an explicit output target")
        score -= 15

    if any(symbol in prompt_text for symbol in ["```", "<", ">", "::"]):
        strengths.append("Uses structured delimiters or formatting hints")
    else:
        weaknesses.append("No obvious formatting or delimiter guidance")
        suggestions.append("Use sections, bullet points, or code fences when structure matters")
        score -= 8

    if any(keyword in normalized.lower() for keyword in ["json", "sql", "csv", "table", "schema"]):
        strengths.append("Mentions a structured output or data format")
    else:
        weaknesses.append("Structured output requirements are not explicit")
        suggestions.append("State the exact output schema or format you expect")
        score -= 10

    if any(keyword in normalized.lower() for keyword in ["example", "few-shot", "for example"]):
        strengths.append("Includes examples that can anchor the output")
    else:
        weaknesses.append("No few-shot examples were found")
        suggestions.append("Add one or two examples for edge cases or expected style")
        score -= 7

    if task_type == "sql_generation" and "sql" not in normalized.lower():
        weaknesses.append("Task type and prompt content are inconsistent for SQL generation")
        score -= 5

    if len(normalized) > 1000:
        weaknesses.append("Prompt is long and may carry unnecessary context")
        suggestions.append("Trim the prompt or split instructions from background context")
        score -= 5

    if not strengths:
        strengths.append("Prompt is readable and can be evaluated automatically")

    score = max(0.0, min(100.0, score))
    return score, strengths, weaknesses, suggestions


def _provider_key_for_model(db: Session, project_id: str, model_id: str) -> ProviderResolution:
    model = get_model(model_id)
    if not model:
        raise ValueError(f"Model '{model_id}' is not enabled or does not exist")

    provider_key = (
        db.query(ProviderKey)
        .filter(ProviderKey.project_id == project_id, ProviderKey.provider_name == model.provider)
        .one_or_none()
    )
    return ProviderResolution(provider_name=model.provider, model_id=model.id, provider_key=provider_key, model_config=model)


def _resolve_prompt_text(file_name: str | None, raw_bytes: bytes, provided_text: str | None) -> str:
    if provided_text:
        return provided_text.strip()

    text = raw_bytes.decode("utf-8")
    suffix = Path(file_name or "").suffix.lower()
    if suffix == ".json":
        payload = json.loads(text)
        if isinstance(payload, list):
            first = payload[0] if payload else {}
            if isinstance(first, dict):
                return str(first.get("prompt") or first.get("text") or first)
            return str(first)
        if isinstance(payload, dict):
            return str(payload.get("prompt") or payload.get("text") or payload)
        return str(payload)
    if suffix == ".csv":
        rows = list(csv.DictReader(text.splitlines()))
        if rows:
            row = rows[0]
            return str(row.get("prompt") or row.get("text") or row)
        return text
    return text


def _call_openai_chat(api_key: str, model_id: str, prompt_text: str, temperature: float = 0.2) -> str:
    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model_id,
            "messages": [
                {"role": "system", "content": "You are a concise prompt quality judge."},
                {"role": "user", "content": prompt_text},
            ],
            "temperature": temperature,
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["choices"][0]["message"]["content"]


def _call_ollama_chat(base_url: str, model_id: str, prompt_text: str) -> str:
    base = base_url.rstrip("/")
    response = httpx.post(
        f"{base}/api/chat",
        json={
            "model": model_id,
            "messages": [
                {"role": "system", "content": "You are a concise prompt quality judge."},
                {"role": "user", "content": prompt_text},
            ],
            "stream": False,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    payload = response.json()
    message = payload.get("message") or {}
    return str(message.get("content") or payload.get("response") or "")


def _judge_prompt_with_model(db: Session, project_id: str, judge_model: str, prompt_text: str) -> tuple[str | None, str | None]:
    try:
        resolution = _provider_key_for_model(db, project_id, judge_model)
    except ValueError:
        return None, "fallback"

    if not resolution.provider_key:
        return None, "fallback"

    provider = resolution.provider_name
    try:
        if provider == "openai":
            api_key = decrypt_text(resolution.provider_key.encrypted_api_key or "")
            judge_output = _call_openai_chat(api_key, judge_model, prompt_text)
            return judge_output, None
        if provider == "ollama":
            if not resolution.provider_key.ollama_base_url:
                return None, "fallback"
            judge_output = _call_ollama_chat(resolution.provider_key.ollama_base_url, judge_model, prompt_text)
            return judge_output, None
    except Exception:
        return None, "fallback"
    return None, "fallback"


def analyze_prompt(
    db: Session,
    *,
    project_id: str,
    task_type: str,
    prompt_text: str,
    judge_model: str,
    source_prompt_id: str | None = None,
) -> tuple[Prompt, PromptAnalysis]:
    version = _prompt_family_version(db, project_id, source_prompt_id)
    base_score, strengths, weaknesses, suggestions = analyze_prompt_text(prompt_text, task_type)
    token_count = estimate_tokens(prompt_text, judge_model)
    estimated_cost = estimate_cost(judge_model, token_count, 256)

    judge_prompt = (
        "Evaluate the following prompt for clarity, structure, edge cases, and failure behavior. "
        "Return concise improvement advice.\n\n"
        f"Task type: {task_type}\n\nPrompt:\n{prompt_text}"
    )
    judge_output, mode = _judge_prompt_with_model(db, project_id, judge_model, judge_prompt)
    if judge_output:
        suggestions = list(dict.fromkeys(suggestions + [f"Judge feedback: {judge_output[:240].strip()}"]))
        strengths.append("Judge model was available for live feedback")
        base_score = min(100.0, base_score + 5.0)
    elif mode == "fallback":
        strengths.append("Used deterministic fallback analysis")

    analysis = PromptAnalysis(
        quality_score=base_score,
        strengths=list(dict.fromkeys(strengths)),
        weaknesses=list(dict.fromkeys(weaknesses)),
        suggested_improvements=list(dict.fromkeys(suggestions)),
        analysis_json={
            "task_type": task_type,
            "judge_model": judge_model,
            "judge_output": judge_output,
            "analysis_mode": "live" if judge_output else "fallback",
        },
        estimated_tokens=token_count,
        estimated_cost_usd=estimated_cost,
        judge_model=judge_model,
    )

    prompt = Prompt(
        project_id=project_id,
        source_prompt_id=source_prompt_id,
        version=version,
        raw_text=prompt_text,
        task_type=task_type,
        quality_score=analysis.quality_score,
        estimated_tokens=analysis.estimated_tokens,
        estimated_cost_usd=analysis.estimated_cost_usd,
        judge_model=judge_model,
        analysis_json=analysis.analysis_json,
    )
    db.add(prompt)
    db.flush()
    return prompt, analysis


def _compose_generation_input(prompt_text: str, test_input: dict[str, Any] | None) -> str:
    if not test_input:
        return prompt_text
    pieces = [prompt_text.strip(), "", f"Input: {test_input.get('input', '')}".strip()]
    context = test_input.get("context")
    reference = test_input.get("reference_answer")
    if context:
        pieces.extend([f"Context: {context}"])
    if reference:
        pieces.extend([f"Reference Answer: {reference}"])
    return "\n".join(piece for piece in pieces if piece is not None)


def _generate_with_provider(
    provider: str,
    provider_key: ProviderKey | None,
    model_id: str,
    input_text: str,
    temperature: float,
) -> tuple[str, dict[str, Any]]:
    if provider == "ollama":
        base_url = (provider_key.ollama_base_url if provider_key else None) or "http://localhost:11434"
        response = httpx.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={"model": model_id, "prompt": input_text, "stream": False, "options": {"temperature": temperature}},
            timeout=120.0,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload.get("response") or ""), payload

    api_key = decrypt_text(provider_key.encrypted_api_key or "") if provider_key and provider_key.encrypted_api_key else ""
    if provider == "openai":
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model_id,
                "messages": [
                    {"role": "system", "content": "Follow the user's instructions exactly."},
                    {"role": "user", "content": input_text},
                ],
                "temperature": temperature,
            },
            timeout=120.0,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"], payload

    raise ValueError(f"Unsupported provider '{provider}' for live generation")


def _row_metric(raw_output: str, reference_answer: str | None) -> tuple[float | None, float | None, float | None]:
    if reference_answer:
        similarity = SequenceMatcher(None, normalize_whitespace(raw_output), normalize_whitespace(reference_answer)).ratio()
        return round(similarity * 100.0, 2), round(similarity * 100.0, 2), None
    heuristic = analyze_prompt_text(raw_output[:1000], "open_ended")[0]
    return heuristic, heuristic, None


def run_experiment(
    db: Session,
    *,
    project_id: str,
    prompt_ids: list[str],
    model_ids: list[str],
    task_type: str,
    test_inputs: list[dict[str, Any]],
    temperature: float,
) -> ExperimentRunResult:
    prompts = (
        db.query(Prompt)
        .filter(Prompt.project_id == project_id, Prompt.id.in_(prompt_ids))
        .order_by(Prompt.version.asc())
        .all()
    )
    if len(prompts) != len(prompt_ids):
        missing = sorted(set(prompt_ids) - {prompt.id for prompt in prompts})
        raise ValueError(f"Prompt(s) not found: {', '.join(missing)}")

    rows: list[dict[str, Any]] = []
    for model_id in model_ids:
        resolution = _provider_key_for_model(db, project_id, model_id)
        if resolution.provider_name != "ollama" and not resolution.provider_key:
            raise ValueError(f"Provider '{resolution.provider_name}' is not configured for model '{model_id}'")
        for prompt in prompts:
            for index, test_input in enumerate(test_inputs or [{}]):
                start = time.perf_counter()
                output_text = ""
                error_message: str | None = None
                payload: dict[str, Any] | None = None
                try:
                    generation_input = _compose_generation_input(prompt.raw_text, test_input)
                    output_text, payload = _generate_with_provider(
                        resolution.provider_name,
                        resolution.provider_key,
                        model_id,
                        generation_input,
                        temperature,
                    )
                except Exception as exc:
                    error_message = str(exc)
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                input_tokens = estimate_tokens(_compose_generation_input(prompt.raw_text, test_input), model_id)
                output_tokens = estimate_tokens(output_text or error_message or "", model_id)
                cost_usd = estimate_cost(model_id, input_tokens, output_tokens)
                quality_score, answer_relevancy, faithfulness = _row_metric(output_text, test_input.get("reference_answer"))
                accuracy = answer_relevancy if test_input.get("reference_answer") else None
                rows.append(
                    {
                        "model_id": model_id,
                        "provider": resolution.provider_name,
                        "prompt_id": prompt.id,
                        "input_index": index,
                        "input": test_input,
                        "raw_output": output_text,
                        "raw_provider_payload": payload,
                        "latency_ms": round(elapsed_ms, 2),
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cost_usd": cost_usd,
                        "quality_score": quality_score,
                        "accuracy": accuracy,
                        "answer_relevancy": answer_relevancy,
                        "faithfulness": faithfulness,
                        "error": error_message,
                    }
                )

    total_cost = round(sum(row["cost_usd"] for row in rows), 6)
    avg_quality = round(sum((row["quality_score"] or 0.0) for row in rows) / max(len(rows), 1), 2)
    avg_accuracy = None
    accuracy_values = [row["accuracy"] for row in rows if row["accuracy"] is not None]
    if accuracy_values:
        avg_accuracy = round(sum(accuracy_values) / len(accuracy_values), 2)
    latencies = [row["latency_ms"] for row in rows]
    summary = {
        "row_count": len(rows),
        "total_cost_usd": total_cost,
        "quality_score": avg_quality,
        "accuracy": avg_accuracy,
        "latency_p50_ms": round(sorted(latencies)[len(latencies) // 2], 2) if latencies else 0.0,
        "latency_p95_ms": round(sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)], 2) if latencies else 0.0,
        "input_tokens": sum(row["input_tokens"] for row in rows),
        "output_tokens": sum(row["output_tokens"] for row in rows),
    }
    return ExperimentRunResult(rows=rows, summary=summary)


def log_experiment_to_mlflow(
    experiment: Experiment,
    *,
    task_type: str,
    prompt_ids: list[str],
    model_ids: list[str],
    test_inputs: list[dict[str, Any]],
    results: dict[str, Any],
) -> str | None:
    try:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment("Optiq")
        with mlflow.start_run(run_name=f"experiment-{experiment.id}") as run:
            mlflow.log_params(
                {
                    "experiment_id": experiment.id,
                    "task_type": task_type,
                    "prompt_ids": ",".join(prompt_ids),
                    "model_ids": ",".join(model_ids),
                }
            )
            for key, value in results.get("summary", {}).items():
                if isinstance(value, (int, float)) and value is not None:
                    mlflow.log_metric(key, float(value))
            with tempfile.TemporaryDirectory() as temp_dir:
                artifact_path = Path(temp_dir) / "experiment-results.json"
                artifact_path.write_text(
                    json.dumps({"test_inputs": test_inputs, "results": results}, indent=2),
                    encoding="utf-8",
                )
                mlflow.log_artifact(str(artifact_path))
            return run.info.run_id
    except Exception:
        return None


def list_project_provider_views(db: Session, project_id: str) -> list[dict[str, Any]]:
    provider_rows = (
        db.query(ProviderKey)
        .filter(ProviderKey.project_id == project_id)
        .order_by(ProviderKey.provider_name.asc())
        .all()
    )
    configured = {row.provider_name: row for row in provider_rows}
    views: list[dict[str, Any]] = []
    for provider_name in ["openai", "ollama", "anthropic", "google"]:
        provider_cfg = get_provider_config(provider_name)
        if not provider_cfg:
            continue
        models = [model for model in list_models(provider=provider_name, include_disabled=False)]
        provider_key = configured.get(provider_name)
        views.append(
            {
                "provider_name": provider_name,
                "configured": provider_key is not None,
                "has_api_key": bool(provider_key and provider_key.encrypted_api_key),
                "ollama_base_url": provider_key.ollama_base_url if provider_key else None,
                "available_models": [
                    {
                        "id": model.id,
                        "display_name": model.display_name,
                        "default_temperature": model.default_temperature,
                        "max_tokens": model.max_tokens,
                        "pricing": None
                        if not model.pricing
                        else {
                            "input_per_1m": model.pricing.input_per_1m,
                            "output_per_1m": model.pricing.output_per_1m,
                        },
                    }
                    for model in models
                ],
            }
        )
    return views


def score_recommendations(options: list[dict[str, Any]], request: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], str]:
    excluded: list[dict[str, Any]] = []
    viable: list[dict[str, Any]] = []

    for option in options:
        reasons: list[str] = []
        if request.get("max_cost") is not None and option.get("cost_usd", 0.0) > request["max_cost"]:
            reasons.append("exceeds max cost")
        if request.get("max_latency_ms") is not None and option.get("latency_ms", 0.0) > request["max_latency_ms"]:
            reasons.append("exceeds max latency")
        if request.get("min_quality_score") is not None and (option.get("quality_score") or 0.0) < request["min_quality_score"]:
            reasons.append("below minimum quality score")
        if request.get("requires_structured_json") and not option.get("structured_output", False):
            reasons.append("structured JSON required")

        if reasons:
            excluded.append({**option, "reasons": reasons})
        else:
            viable.append(option)

    if not viable:
        if options:
            viable = [max(options, key=lambda row: row.get("quality_score") or 0.0)]
        else:
            raise ValueError("No candidate options available")

    max_cost = max((option.get("cost_usd") or 0.0) for option in viable) or 1.0
    max_latency = max((option.get("latency_ms") or 0.0) for option in viable) or 1.0
    max_quality = max((option.get("quality_score") or 0.0) for option in viable) or 1.0

    weights = request.get("weights") or {}
    if request.get("goal") == "cheapest":
        weights = {"cost": 0.6, "latency": 0.2, "quality": 0.2}
    elif request.get("goal") == "fastest":
        weights = {"cost": 0.2, "latency": 0.6, "quality": 0.2}
    elif request.get("goal") == "highest_quality":
        weights = {"cost": 0.2, "latency": 0.2, "quality": 0.6}
    else:
        weights = {"cost": weights.get("cost", 0.33), "latency": weights.get("latency", 0.33), "quality": weights.get("quality", 0.34)}

    ranked: list[dict[str, Any]] = []
    for option in viable:
        normalized_cost = 1.0 - ((option.get("cost_usd") or 0.0) / max_cost)
        normalized_latency = 1.0 - ((option.get("latency_ms") or 0.0) / max_latency)
        normalized_quality = (option.get("quality_score") or 0.0) / max_quality
        score = (
            normalized_cost * weights["cost"]
            + normalized_latency * weights["latency"]
            + normalized_quality * weights["quality"]
        )
        ranked.append({**option, "overall_score": round(score * 100.0, 2)})

    ranked.sort(key=lambda row: row["overall_score"], reverse=True)
    top = ranked[0]
    justification = (
        f"Selected {top.get('model_id')} because it balances quality ({top.get('quality_score')}) "
        f"with latency ({top.get('latency_ms')} ms) and cost (${top.get('cost_usd')})."
    )
    return ranked, excluded, top, justification


def build_experiment_summary(experiment: Experiment) -> dict[str, Any]:
    return {
        "id": experiment.id,
        "project_id": experiment.project_id,
        "status": experiment.status,
        "task_type": experiment.task_type,
        "prompt_ids": list(experiment.prompt_ids_json or []),
        "model_ids": list(experiment.model_ids_json or []),
        "mlflow_run_id": experiment.mlflow_run_id,
        "test_inputs": experiment.test_inputs_json,
        "results": experiment.results_json,
        "created_at": experiment.created_at.isoformat() if experiment.created_at else None,
    }


def persist_recommendation(
    db: Session,
    *,
    project_id: str,
    experiment_id: str | None,
    request_payload: dict[str, Any],
    recommended_config: dict[str, Any],
    excluded_options: list[dict[str, Any]],
    ranked_options: list[dict[str, Any]],
    justification: str,
) -> Recommendation:
    recommendation = Recommendation(
        project_id=project_id,
        experiment_id=experiment_id,
        request_payload=request_payload,
        recommended_config=recommended_config,
        excluded_options=excluded_options,
        ranked_options=ranked_options,
        justification=justification,
    )
    db.add(recommendation)
    db.flush()
    return recommendation
