from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.adapters.base import GenerateResult
from app.adapters.retries import with_retries
from app.main import app
from app.services import advisor, phase1
from app.services.evaluation import aggregate_rows, evaluate_row, valid_json_object
from app.services.phase1 import _compose_generation_input, estimate_cost, score_recommendations


@pytest.fixture(autouse=True)
def offline_tokens(monkeypatch):
    monkeypatch.setattr(advisor, "estimate_tokens", lambda text, *_args: len(text) // 4)
    monkeypatch.setattr(phase1, "estimate_tokens", lambda text, *_args: len(text) // 4)


def test_public_prompt_advice_does_not_call_providers(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Advice must not instantiate a provider adapter")

    monkeypatch.setattr(phase1.AdapterFactory, "from_resolution", forbidden)
    with TestClient(app) as client:
        response = client.post("/api/v1/advice", json={
            "prompt": "Write an essay about remote work.", "baseline_model_id": "claude-opus-4-6",
        })
    assert response.status_code == 200
    data = response.json()
    assert data["outcome"] == "suggested_starting_model"
    assert data["advice_cost_usd"] == 0
    assert data["recommended"]["tier"] == "budget"
    assert data["baseline"]["estimated_savings_usd"] > 0
    assert "untested" in " ".join(data["limitations"]).lower()


@pytest.mark.parametrize("text", ["Do it.", "Write code for an agent.", "Write an essay with verified citations about today's news."])
def test_unsupported_and_ambiguous_tasks_do_not_get_a_winner(text):
    result = advisor.advise({"prompt": text})
    assert result["outcome"] == "insufficient_information"
    assert result["recommended"] is None


def test_requirements_and_local_operating_cost_are_explicit():
    result = advisor.advise({"prompt": "Write a short email.", "local_only": True})
    assert result["recommended"]["provider"] == "ollama"
    assert "operating costs" in result["recommended"]["limitation"]
    result = advisor.advise({"prompt": "Write a short email.", "allowed_providers": ["openai"], "max_cost_usd": 0})
    assert result["outcome"] == "no_suitable_supported_model"
    assert result["recommended"] is None


def test_quality_preference_raises_curated_tier_without_claiming_accuracy():
    result = advisor.advise({"prompt": "Write a nuanced technical essay.", "preference": "quality"})
    assert result["recommended"]["tier"] in {"balanced", "premium"}
    assert "quality_score" not in result["recommended"]


def test_unknown_paid_pricing_is_not_free():
    with pytest.raises(ValueError, match="unknown"):
        estimate_cost("unregistered-paid-model", 100, 100)


def test_generation_boundary_never_contains_reference():
    generated = _compose_generation_input("Extract the name.", {
        "input": "Customer: Alice", "context": "Customer record", "reference_answer": "secret-reference-only",
    })
    assert "Alice" in generated and "Customer record" in generated
    assert "secret-reference-only" not in generated
    assert "Reference Answer" not in generated


@pytest.mark.parametrize("text", ['{"a":', '{"a":1} trailing', '{"a":NaN}', '{"a":1,"a":2}', '```json\n{}\n```'])
def test_structured_validation_rejects_partial_or_nonstandard_json(text):
    assert not valid_json_object(text)


def test_reference_checks_parse_json_and_preserve_case_and_types():
    common = dict(prompt_text="Extract data", task_type="extraction", adapter=None, openai_key=None)
    reference = {"reference_answer": '{"name":"Alice","id":1}'}
    assert evaluate_row(**common, test_input=reference, output_text='{"id":1,"name":"Alice"}')["accuracy"] == 100
    assert evaluate_row(**common, test_input=reference, output_text='{"id":1,"name":"alice"}')["accuracy"] == 0
    assert evaluate_row(**common, test_input=reference, output_text='{"id":"1","name":"Alice"}')["accuracy"] == 0


def test_subjective_evaluation_has_no_hidden_judge_or_embedding_calls():
    class ForbiddenAdapter:
        def generate(self, **_kwargs):
            pytest.fail("Hidden judge call")

        def embed(self, *_args):
            pytest.fail("Hidden embedding call")

    metrics = evaluate_row(prompt_text="Write an essay", test_input={}, output_text="An essay.",
                           task_type="writing", adapter=ForbiddenAdapter(), openai_key="configured")
    assert metrics["quality_score"] is None
    assert metrics["eval_engine"] == "user_review_required"


def test_no_candidate_is_restored_after_hard_requirement_failure():
    ranked, excluded, top, _ = score_recommendations([
        {"model_id": "expensive", "cost_usd": 1, "quality_score": 100, "latency_ms": 10},
    ], {"goal": "cheapest", "max_cost": 0.1})
    assert not ranked and excluded
    assert top["usable"] is False and top["model_id"] is None
    assert top["outcome"] == "no_feasible_configuration"


def test_unknown_quality_cannot_pass_quality_requirement():
    ranked, _, top, _ = score_recommendations([
        {"model_id": "unknown", "cost_usd": 0.01, "quality_score": None, "latency_ms": 10},
    ], {"min_quality_score": 0})
    assert not ranked
    assert top["outcome"] == "insufficient_evidence"


def test_aggregate_keeps_failures_and_unknown_cost():
    summary = aggregate_rows([
        {"latency_ms": 1, "cost_usd": 0.01, "quality_score": 100, "error": None},
        {"latency_ms": 2, "cost_usd": None, "quality_score": None, "error": "timeout"},
    ])
    assert summary["quality_score"] == 50
    assert summary["total_cost_usd"] is None
    assert summary["known_cost_usd"] == 0.01
    assert summary["failed_rows"] == 1


def test_budgeted_execution_disables_unreserved_retries_and_keeps_error_cost_unresolved(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        SimpleNamespace(id="p", version=1, raw_text="Write an email", task_type="writing"),
    ]
    resolution = SimpleNamespace(provider_name="openai", provider_key=None, model_config=SimpleNamespace(max_tokens=4096))
    monkeypatch.setattr(phase1, "_provider_key_for_model", lambda *_args: resolution)
    calls = []

    class FailingAdapter:
        def generate(self, **_kwargs):
            def fail():
                calls.append(1)
                req = httpx.Request("POST", "https://example.com")
                raise httpx.HTTPStatusError("unavailable", request=req, response=httpx.Response(503, request=req))
            return with_retries(fail, base_delay=0)

    monkeypatch.setattr(phase1.AdapterFactory, "from_resolution", lambda *_args: FailingAdapter())
    result = phase1.run_experiment(db, project_id="project", prompt_ids=["p"], model_ids=["gpt-4o-mini"],
                                   task_type="writing", test_inputs=[], temperature=0, budget_usd=1)
    assert len(calls) == 1
    assert result.rows[0]["cost_usd"] is None
    assert result.summary["committed_cost_usd"] > 0


def test_budget_stops_new_work_when_reported_usage_exceeds_reservation(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        SimpleNamespace(id="p", version=1, raw_text="Write an email", task_type="writing"),
    ]
    resolution = SimpleNamespace(provider_name="openai", provider_key=None, model_config=SimpleNamespace(max_tokens=4096))
    monkeypatch.setattr(phase1, "_provider_key_for_model", lambda *_args: resolution)
    calls = []

    class OvershootAdapter:
        def generate(self, **_kwargs):
            calls.append(1)
            return GenerateResult(text="Hello", input_tokens=1_000_000, output_tokens=1)

    monkeypatch.setattr(phase1.AdapterFactory, "from_resolution", lambda *_args: OvershootAdapter())
    result = phase1.run_experiment(db, project_id="project", prompt_ids=["p"], model_ids=["gpt-4o-mini"],
                                   task_type="writing", test_inputs=[{"input": "one"}, {"input": "two"}],
                                   temperature=0, budget_usd=0.01)
    assert len(calls) == 1
    assert result.summary["budget_stopped"] is True
    assert len(result.rows) == 1
