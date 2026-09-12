import httpx

from app.adapters.retries import is_retryable, with_retries
from app.services.evaluation import parse_test_inputs
from app.services.phase1 import estimate_cost, score_recommendations


def test_parse_json_test_inputs() -> None:
    rows = parse_test_inputs('[{"input": "hello", "reference_answer": "hi", "context": "docs"}]')
    assert rows == [{"input": "hello", "reference_answer": "hi", "context": "docs"}]


def test_parse_csv_test_inputs() -> None:
    raw = "input,reference_answer,context\nWhat is 2+2?,4,\n"
    rows = parse_test_inputs(raw)
    assert rows[0]["input"] == "What is 2+2?"
    assert rows[0]["reference_answer"] == "4"


def test_estimate_cost_from_yaml_pricing() -> None:
    cost = estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost == 0.75


def test_constraint_filtering_and_ranking() -> None:
    options = [
        {"model_id": "slow", "cost_usd": 0.01, "latency_ms": 9000, "quality_score": 90, "structured_output": True},
        {"model_id": "cheap", "cost_usd": 0.001, "latency_ms": 400, "quality_score": 70, "structured_output": True},
        {"model_id": "jsonless", "cost_usd": 0.002, "latency_ms": 300, "quality_score": 80, "structured_output": False},
    ]
    ranked, excluded, top, justification = score_recommendations(
        options,
        {"goal": "fastest", "max_latency_ms": 1000, "requires_structured_json": True},
    )
    assert top["model_id"] == "cheap"
    assert any(item["model_id"] == "slow" for item in excluded)
    assert any(item["model_id"] == "jsonless" for item in excluded)
    assert "latency" in justification.lower() or "cheap" in justification.lower()


def test_failed_runs_get_an_honest_justification() -> None:
    ranked, _excluded, top, justification = score_recommendations(
        [
            {"model_id": "mistral", "cost_usd": 0.0, "latency_ms": 11, "quality_score": 0, "failed": True},
            {"model_id": "llama3.2", "cost_usd": 0.0, "latency_ms": 12, "quality_score": 0, "failed": True},
        ],
        {"goal": "cheapest"},
    )
    assert top["model_id"] in {"mistral", "llama3.2"}
    assert "failed" in justification.lower() or "quality is 0" in justification.lower()
    assert ranked


def test_retries_on_transient_status() -> None:
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(503, request=request)
        raise httpx.HTTPStatusError("unavailable", request=request, response=response)

    try:
        with_retries(boom, attempts=3, base_delay=0.0)
    except httpx.HTTPStatusError:
        pass
    assert calls["n"] == 3
    assert is_retryable(httpx.TimeoutException("timeout"))
