from __future__ import annotations

import csv
import io
import json
import logging
import math
import re
from typing import Any

from app.adapters.base import BaseAdapter

logger = logging.getLogger("optiq.eval")

_TOKEN_RE = re.compile(r"[a-z0-9]+")


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


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(_normalize(text).lower()))


def _overlap_score(left: str, right: str) -> float:
    a = _tokens(left)
    b = _tokens(right)
    if not a or not b:
        return 0.0
    return round(100.0 * len(a & b) / len(a | b), 2)


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    n1 = math.sqrt(sum(a * a for a in left))
    n2 = math.sqrt(sum(b * b for b in right))
    if n1 == 0 or n2 == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (n1 * n2)))


def exact_match(output: str, reference: str, task_type: str) -> float | None:
    if task_type not in {"sql_generation", "classification"} and not reference.strip().startswith("{"):
        return None
    left = _normalize(output).lower().rstrip(";")
    right = _normalize(reference).lower().rstrip(";")
    if task_type == "sql_generation" or left.startswith("{") or right.startswith("{"):
        return 100.0 if left == right else 0.0
    return 100.0 if left == right else 0.0


def try_ragas_metrics(question: str, answer: str, context: str | None, openai_key: str | None) -> dict[str, float] | None:
    if not openai_key or not question.strip() or not answer.strip():
        return None
    try:
        import os

        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, faithfulness

        os.environ["OPENAI_API_KEY"] = openai_key
        data: dict[str, list[Any]] = {"question": [question], "answer": [answer]}
        metrics = [answer_relevancy]
        if context:
            data["contexts"] = [[context]]
            metrics.append(faithfulness)
        result = evaluate(Dataset.from_dict(data), metrics=metrics)
        frame = result.to_pandas()
        row = frame.iloc[0].to_dict()
        scores: dict[str, float] = {}
        if "answer_relevancy" in row and row["answer_relevancy"] == row["answer_relevancy"]:
            scores["answer_relevancy"] = round(float(row["answer_relevancy"]) * 100.0, 2)
        if "faithfulness" in row and row["faithfulness"] == row["faithfulness"]:
            scores["faithfulness"] = round(float(row["faithfulness"]) * 100.0, 2)
        return scores or None
    except Exception as exc:
        logger.info("ragas unavailable, using local metrics: %s", exc)
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
    question = str(test_input.get("input") or prompt_text)
    reference = test_input.get("reference_answer")
    context = test_input.get("context")
    ragas = try_ragas_metrics(question, output_text, context, openai_key)

    relevancy = ragas.get("answer_relevancy") if ragas else None
    faithfulness = ragas.get("faithfulness") if ragas else None
    accuracy: float | None = None
    quality: float | None = None
    engine = "ragas" if ragas else "heuristic"

    embeddings = None
    if adapter is not None and (reference or not relevancy):
        embed_inputs = [output_text or " ", str(reference or question)]
        embeddings = adapter.embed(embed_inputs)

    if embeddings and len(embeddings) == 2:
        similarity = round(_cosine(embeddings[0], embeddings[1]) * 100.0, 2)
        if reference:
            accuracy = similarity
        if relevancy is None:
            relevancy = similarity
            engine = "embedding"

    if relevancy is None:
        relevancy = _overlap_score(question, output_text)
    if context and faithfulness is None:
        faithfulness = _overlap_score(output_text, str(context))
    if reference:
        structured = exact_match(output_text, str(reference), task_type)
        accuracy = structured if structured is not None else (accuracy if accuracy is not None else _overlap_score(output_text, str(reference)))
        quality = accuracy
    else:
        quality = _llm_or_heuristic_quality(adapter, prompt_text, output_text, task_type)

    return {
        "quality_score": quality,
        "accuracy": accuracy,
        "answer_relevancy": relevancy,
        "faithfulness": faithfulness,
        "eval_engine": engine,
    }


def _llm_or_heuristic_quality(
    adapter: BaseAdapter | None,
    prompt_text: str,
    output_text: str,
    task_type: str,
    model_id: str | None = None,
) -> float:
    if adapter and output_text.strip():
        judge_prompt = (
            "Score the model output from 0-100 for how well it follows the prompt. "
            "Return JSON only: {\"quality_score\": number, \"reason\": string}.\n\n"
            f"Task type: {task_type}\nPrompt:\n{prompt_text}\n\nOutput:\n{output_text[:4000]}"
        )
        try:
            result = adapter.generate(
                model_id=model_id or _adapter_default_model(adapter),
                prompt=judge_prompt,
                temperature=0.0,
                max_tokens=256,
                system="You are a strict evaluator. Return JSON only.",
            )
            from app.services.phase1 import _extract_json_object, analyze_prompt_text

            parsed = _extract_json_object(result.text)
            if parsed and isinstance(parsed.get("quality_score"), (int, float)):
                return round(max(0.0, min(100.0, float(parsed["quality_score"]))), 2)
        except Exception as exc:
            logger.info("llm-as-judge failed: %s", exc)
    from app.services.phase1 import analyze_prompt_text

    return analyze_prompt_text(output_text[:1000] or " ", task_type or "open_ended")[0]


def _adapter_default_model(adapter: BaseAdapter) -> str:
    if adapter.provider_name == "openai":
        return "gpt-4o-mini"
    if adapter.provider_name == "ollama":
        return "llama3.2"
    if adapter.provider_name == "anthropic":
        return "claude-sonnet-4-20250514"
    if adapter.provider_name in {"google", "gemini"}:
        return "gemini-2.0-flash"
    return "gpt-4o-mini"


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "row_count": 0,
            "total_cost_usd": 0.0,
            "quality_score": 0.0,
            "accuracy": None,
            "answer_relevancy": None,
            "faithfulness": None,
            "latency_p50_ms": 0.0,
            "latency_p95_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
        }

    def _avg(key: str) -> float | None:
        values = [row[key] for row in rows if row.get(key) is not None]
        if not values:
            return None
        return round(sum(values) / len(values), 2)

    latencies = sorted(row["latency_ms"] for row in rows)
    p95_index = max(0, math.ceil(len(latencies) * 0.95) - 1)
    return {
        "row_count": len(rows),
        "total_cost_usd": round(sum(row.get("cost_usd") or 0.0 for row in rows), 6),
        "quality_score": _avg("quality_score") or 0.0,
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
