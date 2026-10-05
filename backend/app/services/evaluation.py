from __future__ import annotations

import csv
import io
import json
import math
from typing import Any

from app.adapters.base import BaseAdapter


def parse_test_inputs(raw: str | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [_normalize_test_row(item) for item in raw]
    text = raw.strip()
    if not text:
        return []
    if text.startswith("[") or text.startswith("{"):
        payload = json.loads(text)
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            raise ValueError("Test inputs JSON must be an object or array")
        return [_normalize_test_row(item) for item in payload]
    reader = csv.DictReader(io.StringIO(text))
    rows = [_normalize_test_row(dict(row)) for row in reader]
    if not rows:
        raise ValueError("CSV test inputs must include at least one data row")
    return rows


def _normalize_test_row(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"input": str(item), "reference_answer": None, "context": None}
    return {
        "input": str(item.get("input") or item.get("prompt") or item.get("text") or ""),
        "reference_answer": item.get("reference_answer") or item.get("reference") or None,
        "context": item.get("context") or None,
    }


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _strict_json(text: str) -> Any:
    def reject_constant(value):
        raise ValueError(f"Non-JSON constant: {value}")

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    return json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique_keys)


def valid_json_object(text: str) -> bool:
    try:
        return isinstance(_strict_json(text), dict)
    except (ValueError, TypeError):
        return False


def exact_match(output: str, reference: str, task_type: str) -> float | None:
    if reference.strip().startswith(("{", "[")):
        try:
            # Compare parsed values without case-folding or numeric coercion.
            left = json.dumps(_strict_json(output), sort_keys=True, ensure_ascii=False)
            right = json.dumps(_strict_json(reference), sort_keys=True, ensure_ascii=False)
            return 100.0 if left == right else 0.0
        except (ValueError, TypeError):
            return 0.0
    if task_type in {"classification", "sql_generation"}:
        return 100.0 if _normalize(output) == _normalize(reference) else 0.0
    return None


def try_ragas_metrics(*_args, **_kwargs) -> None:
    """Legacy compatibility: default evaluation never starts paid judge calls."""
    return None


def evaluate_row(
    *,
    prompt_text: str,
    test_input: dict[str, Any],
    output_text: str,
    task_type: str,
    adapter: BaseAdapter | None,
    openai_key: str | None,
) -> dict[str, Any]:
    # An answer's style, lexical overlap, or prompt-writing score does not prove
    # correctness. Use deterministic reference checks only; subjective work
    # stays unscored for the user to inspect. No embeddings or hidden judges.
    reference = test_input.get("reference_answer")
    accuracy = exact_match(output_text, str(reference), task_type) if reference is not None else None
    return {
        "quality_score": accuracy,
        "accuracy": accuracy,
        "answer_relevancy": None,
        "faithfulness": None,
        "structured_output": valid_json_object(output_text),
        "eval_engine": "deterministic_reference" if accuracy is not None else "user_review_required",
    }


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "row_count": 0,
            "total_cost_usd": 0.0,
            "quality_score": None,
            "accuracy": None,
            "answer_relevancy": None,
            "faithfulness": None,
            "latency_p50_ms": 0.0,
            "latency_p95_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
        }

    def _avg(key: str) -> float | None:
        known = [row.get(key) for row in rows if not row.get("error")]
        if not known or any(value is None for value in known):
            return None
        values = [0.0 if row.get("error") else row[key] for row in rows]
        if not values:
            return None
        return round(sum(values) / len(values), 2)

    latencies = sorted(row["latency_ms"] for row in rows)
    p95_index = max(0, math.ceil(len(latencies) * 0.95) - 1)
    return {
        "row_count": len(rows),
        "total_cost_usd": round(sum(row["cost_usd"] for row in rows), 6) if all(row.get("cost_usd") is not None for row in rows) else None,
        "known_cost_usd": round(sum(row.get("cost_usd") or 0.0 for row in rows), 6),
        "unresolved_cost_rows": sum(row.get("cost_usd") is None or bool(row.get("error")) for row in rows),
        "quality_score": _avg("quality_score"),
        "accuracy": _avg("accuracy"),
        "answer_relevancy": _avg("answer_relevancy"),
        "faithfulness": _avg("faithfulness"),
        "latency_p50_ms": round(latencies[len(latencies) // 2], 2),
        "latency_p95_ms": round(latencies[p95_index], 2),
        "input_tokens": sum(row.get("input_tokens") or 0 for row in rows),
        "output_tokens": sum(row.get("output_tokens") or 0 for row in rows),
        "failed_rows": sum(1 for row in rows if row.get("error")),
    }


def per_model_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((row["model_id"], row["prompt_id"]), []).append(row)
    summaries: list[dict[str, Any]] = []
    for (model_id, prompt_id), group in grouped.items():
        item = aggregate_rows(group)
        item["model_id"] = model_id
        item["prompt_id"] = prompt_id
        item["provider"] = group[0].get("provider")
        summaries.append(item)
    return summaries
