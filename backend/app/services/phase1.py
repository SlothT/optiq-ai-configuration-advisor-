from __future__ import annotations

import csv
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tiktoken
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.adapters.base import ProviderResolution
from app.adapters.factory import AdapterFactory, resolve_provider
from app.adapters.ollama_adapter import list_installed_ollama_models, normalize_ollama_base_url
from app.adapters.retries import single_attempt
from app.config.model_registry import get_model, get_provider_config, list_models, model_is_local, resolve_model_info
from app.core.config import settings
from app.models.domain import Experiment, Prompt, ProviderKey, Recommendation
from app.services.evaluation import aggregate_rows, evaluate_row, per_model_summary

TASK_KEYWORDS = {
    "summarization": ["summary", "summarize", "condense"],
    "qa": ["question", "answer", "qa"],
    "sql_generation": ["sql", "query", "database"],
    "classification": ["classify", "label", "category"],
    "open_ended": [],
}

CONTEXT_MARKER = "--- Context from uploaded files ---"
MAX_CONTEXT_FILE_BYTES = 200_000
MAX_CONTEXT_TOTAL_BYTES = 1_048_576
ALLOWED_CONTEXT_SUFFIXES = {".md", ".markdown", ".txt", ".csv", ".json", ".yml", ".yaml"}


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
    prompts: list[Prompt]



def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def estimate_tokens(text: str, model_id: str | None = None) -> int:
    try:
        encoding = tiktoken.encoding_for_model(model_id or "gpt-4o-mini")
    except Exception:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Tokenizer data may not be cached on an offline contributor machine.
            return math.ceil(len(text) / 4)
    return len(encoding.encode(text))


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    model = resolve_model_info(model_id) or get_model(model_id)
    if model and model.provider == "ollama":
        return 0.0
    if not model or not model.pricing:
        raise ValueError(f"Pricing is unknown for {model_id}; it cannot be treated as free")
    input_cost = (input_tokens / 1_000_000) * model.pricing.input_per_1m
    output_cost = (output_tokens / 1_000_000) * model.pricing.output_per_1m
    return round(input_cost + output_cost, 6)


def compose_prompt_with_context(
    user_prompt: str,
    attachments: list[tuple[str | None, bytes]],
) -> tuple[str, str, dict[str, Any]]:
    user_prompt = (user_prompt or "").strip()
    skipped: list[str] = []
    included: list[str] = []
    parts: list[str] = []
    total_bytes = 0

    for file_name, raw_bytes in attachments:
        name = (file_name or "upload").strip() or "upload"
        suffix = Path(name).suffix.lower()
        if suffix not in ALLOWED_CONTEXT_SUFFIXES:
            skipped.append(f"{name}: unsupported type")
            continue
        if len(raw_bytes) > MAX_CONTEXT_FILE_BYTES:
            skipped.append(f"{name}: larger than 200KB")
            continue
        if total_bytes + len(raw_bytes) > MAX_CONTEXT_TOTAL_BYTES:
            skipped.append(f"{name}: skipped because total upload size exceeds 1MB")
            continue
        try:
            decoded = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            skipped.append(f"{name}: not valid UTF-8 text")
            continue
        total_bytes += len(raw_bytes)
        included.append(name)
        parts.append(f"### {name}\n{decoded.strip()}")

    context_text = "\n\n".join(parts)
    if context_text:
        composed = f"{user_prompt}\n\n{CONTEXT_MARKER}\n{context_text}".strip()
    else:
        composed = user_prompt
    meta = {
        "context_files": included,
        "skipped_files": skipped,
        "prompt_chars": len(user_prompt),
        "context_chars": len(context_text),
    }
    return composed, context_text, meta


def _prompt_family_version(db: Session, project_id: str, source_prompt_id: str | None) -> int:
    if source_prompt_id:
        source = db.query(Prompt).filter(Prompt.id == source_prompt_id, Prompt.project_id == project_id).one_or_none()
        if not source:
            raise ValueError("Prompt not found for re-analysis")
    latest = (
        db.query(func.max(Prompt.version))
        .filter(Prompt.project_id == project_id)
        .scalar()
    )
    return int(latest or 0) + 1


def analyze_prompt_text(
    prompt_text: str,
    task_type: str,
    context_text: str = "",
) -> tuple[float, list[str], list[str], list[str]]:
    normalized = normalize_whitespace(prompt_text)
    strengths: list[str] = []
    weaknesses: list[str] = []
    suggestions: list[str] = []
    score = 100.0
    has_context = bool(context_text.strip())

    word_count = len(normalized.split())
    if word_count >= 75:
        strengths.append("Enough detail for a robust model response")
    elif word_count < 25:
        weaknesses.append("Prompt is very short and may be underspecified")
        suggestions.append("Add task context, constraints, and an explicit output target")
        score -= 15
        if has_context:
            suggestions.append("Say how the model should use the attached documents")
            score += 8

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

    if has_context:
        strengths.append("Supporting documents were attached as context")

    if not strengths:
        strengths.append("Prompt is readable and can be evaluated automatically")

    score = max(0.0, min(100.0, score))
    return score, strengths, weaknesses, suggestions


def _provider_key_for_model(db: Session, project_id: str, model_id: str) -> ProviderResolution:
    return resolve_provider(db, project_id, model_id)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _resolve_prompt_text(file_name: str | None, raw_bytes: bytes, provided_text: str | None) -> str:
    if raw_bytes:
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
            return text.strip()
        return text.strip()
    return (provided_text or "").strip()


def analyze_prompt(
    db: Session,
    *,
    project_id: str,
    task_type: str,
    prompt_text: str,
    judge_model: str,
    source_prompt_id: str | None = None,
    user_prompt: str | None = None,
    context_text: str = "",
    context_meta: dict[str, Any] | None = None,
) -> tuple[Prompt, PromptAnalysis]:
    version = _prompt_family_version(db, project_id, source_prompt_id)
    scored_prompt = (user_prompt or prompt_text).strip()
    base_score, strengths, weaknesses, suggestions = analyze_prompt_text(scored_prompt, task_type, context_text)
    # Prompt review is local and deterministic. No advisory judge calls are billed.
    cost_model = "local-rules"
    prompt_tokens = estimate_tokens(scored_prompt)
    context_tokens = estimate_tokens(context_text) if context_text else 0
    token_count = estimate_tokens(prompt_text)
    estimated_cost = 0.0
    cost_local = True
    judge_output, judge_error = None, None
    resolved_judge = None
    analysis_mode = "local_rules"

    analysis = PromptAnalysis(
        quality_score=base_score,
        strengths=list(dict.fromkeys(strengths)),
        weaknesses=list(dict.fromkeys(weaknesses)),
        suggested_improvements=list(dict.fromkeys(suggestions)),
        analysis_json={
            "task_type": task_type,
            "judge_model": resolved_judge,
            "requested_judge_model": judge_model,
            "judge_output": judge_output,
            "judge_error": judge_error,
            "analysis_mode": analysis_mode,
            "cost_is_local": cost_local,
            "cost_model": cost_model,
            "prompt_tokens": prompt_tokens,
            "context_tokens": context_tokens,
            **(context_meta or {}),
        },
        estimated_tokens=token_count,
        estimated_cost_usd=estimated_cost,
        judge_model=resolved_judge,
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
        judge_model=resolved_judge,
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
    if context:
        pieces.extend([f"Context: {context}"])
    return "\n".join(piece for piece in pieces if piece is not None)


def estimate_experiment_cost(
    db: Session,
    *,
    project_id: str,
    prompt_ids: list[str],
    model_ids: list[str],
    test_inputs: list[dict[str, Any]],
    max_output_tokens: int = 1024,
) -> dict[str, Any]:
    prompts = (
        db.query(Prompt)
        .filter(Prompt.project_id == project_id, Prompt.id.in_(prompt_ids))
        .all()
    )
    if len(prompts) != len(prompt_ids):
        missing = sorted(set(prompt_ids) - {prompt.id for prompt in prompts})
        raise ValueError(f"Prompt(s) not found: {', '.join(missing)}")
    cases = test_inputs or [{}]
    estimated_rows = len(prompts) * len(model_ids) * max(len(cases), 1)
    total = 0.0
    breakdown: list[dict[str, Any]] = []
    for model_id in model_ids:
        resolution = _provider_key_for_model(db, project_id, model_id)
        AdapterFactory.from_resolution(resolution)  # Validate credentials before queueing.
        model_cost = 0.0
        for prompt in prompts:
            for test_input in cases:
                generation_input = _compose_generation_input(prompt.raw_text, test_input)
                input_tokens = math.ceil(estimate_tokens(generation_input, model_id) * 1.25) + 64
                model = resolution.model_config
                output_tokens = min(max_output_tokens or model.max_tokens, model.max_tokens)
                model_cost += 0.0 if model.provider == "ollama" else estimate_cost(model_id, input_tokens, output_tokens)
        breakdown.append({
            "model_id": model_id,
            "estimated_cost_usd": round(model_cost, 6),
            "cost_is_local": resolution.provider_name == "ollama",
            "pricing_source": resolution.model_config.pricing_source,
            "pricing_checked_at": resolution.model_config.pricing_checked_at,
            "input_per_1m": resolution.model_config.pricing.input_per_1m if resolution.model_config.pricing else None,
            "output_per_1m": resolution.model_config.pricing.output_per_1m if resolution.model_config.pricing else None,
        })
        total += model_cost
    local_only = bool(breakdown) and all(item["cost_is_local"] for item in breakdown)
    return {
        "estimated_cost_usd": round(total, 6),
        "estimated_rows": estimated_rows,
        "breakdown": breakdown,
        "cost_is_local": local_only,
        "estimate_basis": "Maximum output tokens, input-token buffer; one call per case, no hidden evaluation or retries",
        "billing_note": "Dispatch estimate, not a provider invoice guarantee; failed calls may have unreported charges",
    }


def run_experiment(
    db: Session,
    *,
    project_id: str,
    prompt_ids: list[str],
    model_ids: list[str],
    task_type: str,
    test_inputs: list[dict[str, Any]],
    temperature: float,
    max_output_tokens: int = 1024,
    budget_usd: float | None = None,
    record_progress=None,
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
    committed_cost = 0.0
    stopped = False
    for model_id in model_ids:
        resolution = _provider_key_for_model(db, project_id, model_id)
        adapter = AdapterFactory.from_resolution(resolution)
        max_tokens = min(max_output_tokens, int(getattr(resolution.model_config, "max_tokens", 1024) or 1024))
        for prompt in prompts:
            for index, test_input in enumerate(test_inputs or [{}]):
                start = time.perf_counter()
                output_text = ""
                error_message: str | None = None
                usage_in: int | None = None
                usage_out: int | None = None
                generation_input = _compose_generation_input(prompt.raw_text, test_input)
                reserved_cost = estimate_cost(
                    model_id, math.ceil(estimate_tokens(generation_input, model_id) * 1.25) + 64, max_tokens,
                ) if resolution.provider_name != "ollama" else 0.0
                if budget_usd is not None and committed_cost + reserved_cost > budget_usd + 1e-9:
                    stopped = True
                    break
                if record_progress:
                    record_progress(rows, committed_cost, reserved_cost)
                try:
                    with single_attempt():
                        generated = adapter.generate(
                            model_id=model_id,
                            prompt=generation_input,
                            temperature=temperature,
                            max_tokens=max_tokens,
                        )
                    output_text = generated.text
                    usage_in = generated.input_tokens
                    usage_out = generated.output_tokens
                except Exception as exc:
                    error_message = str(exc)
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                input_tokens = usage_in if usage_in is not None else estimate_tokens(generation_input, model_id)
                output_tokens = usage_out if usage_out is not None else estimate_tokens(output_text or error_message or "", model_id)
                cost_usd = None if error_message else (
                    0.0 if resolution.provider_name == "ollama" else estimate_cost(model_id, input_tokens, output_tokens)
                )
                # Unknown failure charges retain their full reservation.
                committed_cost += reserved_cost if cost_usd is None else cost_usd
                metrics = (
                    evaluate_row(
                        prompt_text=prompt.raw_text,
                        test_input=test_input or {},
                        output_text=output_text,
                        task_type=task_type or prompt.task_type,
                        adapter=adapter,
                        openai_key=None,
                    )
                    if not error_message
                    else {"quality_score": None, "accuracy": None, "answer_relevancy": None, "faithfulness": None, "eval_engine": "skipped"}
                )
                rows.append(
                    {
                        "model_id": model_id,
                        "provider": resolution.provider_name,
                        "prompt_id": prompt.id,
                        "prompt_version": prompt.version,
                        "input_index": index,
                        "input": test_input,
                        "raw_output": output_text,
                        "latency_ms": round(elapsed_ms, 2),
                        "input_tokens": input_tokens if not error_message else 0,
                        "output_tokens": output_tokens if not error_message else 0,
                        "usage_source": "provider" if usage_in is not None and usage_out is not None else "estimated",
                        "reserved_cost_usd": reserved_cost,
                        "cost_status": "unresolved" if error_message else "usage_estimate",
                        "max_output_tokens": max_tokens,
                        "temperature": temperature,
                        "cost_usd": cost_usd,
                        "cost_is_local": model_is_local(model_id) or resolution.provider_name == "ollama",
                        **metrics,
                        "error": error_message,
                    }
                )

                if record_progress:
                    record_progress(rows, committed_cost, 0.0)
            if stopped:
                break
        if stopped:
            break

    summary = aggregate_rows(rows)
    summary["per_model"] = per_model_summary(rows)
    summary["budget_usd"] = budget_usd
    summary["committed_cost_usd"] = round(committed_cost, 6)
    summary["budget_stopped"] = stopped
    summary["advice_cost_usd"] = 0.0
    summary["evaluation_cost_usd"] = 0.0
    summary["billing_note"] = "No automatic retries or paid judges; estimates are not invoices and failed-call charges may be unresolved."
    return ExperimentRunResult(rows=rows, summary=summary, prompts=prompts)


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
        provider_key = configured.get(provider_name)
        status_message = None
        if provider_name == "ollama" and provider_key:
            base_url = normalize_ollama_base_url(
                provider_key.ollama_base_url or settings.ollama_base_url,
                settings.ollama_base_url,
            )
            tags, error = list_installed_ollama_models(base_url)
            registry_by_id = {model.id: model for model in list_models(provider="ollama", include_disabled=False)}
            models_payload = []
            for tag in tags:
                short = tag.split(":", 1)[0]
                registered = registry_by_id.get(tag) or registry_by_id.get(short)
                models_payload.append(
                    {
                        "id": tag,
                        "display_name": registered.display_name if registered else tag,
                        "default_temperature": registered.default_temperature if registered else 0.7,
                        "max_tokens": registered.max_tokens if registered else 4096,
                        "pricing": None,
                    }
                )
            if error:
                status_message = error
            elif not tags:
                status_message = f"Ollama is reachable at {base_url} but no models are installed. Pull a model with `ollama pull`."
        elif provider_key and (provider_name == "ollama" or provider_key.encrypted_api_key):
            models_payload = [
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
                for model in list_models(provider=provider_name, include_disabled=False)
            ]
        else:
            models_payload = []

        views.append(
            {
                "provider_name": provider_name,
                "configured": provider_key is not None,
                "has_api_key": bool(provider_key and provider_key.encrypted_api_key),
                "ollama_base_url": provider_key.ollama_base_url if provider_key else None,
                "available_models": models_payload,
                "status_message": status_message,
            }
        )
    return views


def score_recommendations(options: list[dict[str, Any]], request: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], str]:
    excluded: list[dict[str, Any]] = []
    viable: list[dict[str, Any]] = []

    for option in options:
        reasons: list[str] = []
        if option.get("failed") or option.get("failed_rows", 0):
            reasons.append("generation failed for one or more cases")
        if option.get("cost_usd") is None:
            reasons.append("unknown cost")
        if request.get("goal") == "fastest" and option.get("latency_ms") is None:
            reasons.append("unknown latency")
        if request.get("goal") == "highest_quality" and option.get("quality_score") is None:
            reasons.append("unknown output quality; review outputs or supply references")
        if request.get("max_cost") is not None and option.get("cost_usd") is not None and option["cost_usd"] > request["max_cost"]:
            reasons.append("exceeds max cost")
        if request.get("max_latency_ms") is not None and option.get("latency_ms") is None:
            reasons.append("unknown latency")
        if request.get("max_latency_ms") is not None and option.get("latency_ms") is not None and option["latency_ms"] > request["max_latency_ms"]:
            reasons.append("exceeds max latency")
        if request.get("min_quality_score") is not None and option.get("quality_score") is None:
            reasons.append("unknown output quality")
        if request.get("min_quality_score") is not None and option.get("quality_score") is not None and option["quality_score"] < request["min_quality_score"]:
            reasons.append("below minimum quality score")
        if request.get("requires_structured_json") and not option.get("structured_output", False):
            reasons.append("structured JSON required")

        if reasons:
            excluded.append({**option, "reasons": reasons})
        else:
            viable.append(option)

    if not viable:
        outcome = "insufficient_evidence" if not options or any(
            any("unknown" in reason for reason in item["reasons"]) for item in excluded
        ) else "no_feasible_configuration"
        return [], excluded, {"model_id": None, "usable": False, "outcome": outcome}, (
            "Insufficient evidence to select a model." if outcome == "insufficient_evidence"
            else "No tested configuration meets all requirements. Review the exclusions."
        )

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

    if request.get("goal") == "cheapest":
        ranked.sort(key=lambda row: row["cost_usd"])
    elif request.get("goal") == "fastest":
        ranked.sort(key=lambda row: row.get("latency_ms") or 0)
    elif request.get("goal") == "highest_quality":
        ranked.sort(key=lambda row: row["quality_score"], reverse=True)
    else:
        ranked.sort(key=lambda row: row["overall_score"], reverse=True)
    top = {**ranked[0], "usable": True, "outcome": "tested_on_supplied_cases"}
    if top.get("quality_score") is None:
        justification = (
            f"Selected {top.get('model_id')} on the requested observed cost/latency basis. "
            "Output quality is unscored; review the outputs before choosing. A single comparison is not a reliability guarantee."
        )
    else:
        justification = (
            f"Selected {top.get('model_id')} on the requested basis after hard requirements. "
            f"Reference-check score: {top.get('quality_score')}; observed mean latency: {top.get('latency_ms')} ms; "
            f"mean API cost per case: ${top.get('cost_usd')}. This evidence applies only to the supplied cases."
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
