from app.adapters.ollama_adapter import normalize_ollama_base_url
from app.config.model_registry import model_is_local
from app.services.phase1 import _extract_json_object, analyze_prompt_text, compose_prompt_with_context, estimate_cost


def test_compose_keeps_user_prompt_and_appends_context() -> None:
    composed, context, meta = compose_prompt_with_context(
        "Summarize the attached API design.",
        [("rest_api_design.md", b"# REST API\nUse versioned URLs.")],
    )
    assert composed.startswith("Summarize the attached API design.")
    assert "REST API" in context
    assert "rest_api_design.md" in meta["context_files"]
    assert "--- Context from uploaded files ---" in composed


def test_compose_skips_unsupported_files() -> None:
    composed, context, meta = compose_prompt_with_context(
        "Do the task.",
        [("notes.bin", b"\x00\x01\x02")],
    )
    assert composed == "Do the task."
    assert context == ""
    assert meta["skipped_files"]


def test_short_prompt_with_context_notes_attachments() -> None:
    _score, strengths, _weaknesses, suggestions = analyze_prompt_text(
        "Summarize this.",
        "open_ended",
        context_text="# long design document " * 20,
    )
    assert any("attached" in item.lower() or "context" in item.lower() for item in strengths + suggestions)


def test_rule_analysis_flags_short_unstructured_prompt() -> None:
    score, strengths, weaknesses, suggestions = analyze_prompt_text("Do it.", "open_ended")
    assert score < 90
    assert weaknesses
    assert any("schema" in item.lower() or "format" in item.lower() for item in suggestions)
    assert strengths


def test_extract_json_object_from_fenced_judge_output() -> None:
    payload = _extract_json_object(
        """```json
        {"quality_score": 81, "strengths": ["Clear task"],
         "weaknesses": ["No examples"], "suggested_improvements": ["Add one example"]}
        ```"""
    )
    assert payload is not None
    assert payload["quality_score"] == 81
    assert payload["strengths"] == ["Clear task"]


def test_ollama_url_strips_openai_compatible_suffix() -> None:
    assert normalize_ollama_base_url("http://host.docker.internal:11434/v1") == "http://host.docker.internal:11434"
    assert normalize_ollama_base_url("http://host.docker.internal:11434/v1/chat/completions") == "http://host.docker.internal:11434"


def test_local_models_are_free() -> None:
    assert model_is_local("llama3.2")
    assert estimate_cost("llama3.2", 10_000, 10_000) == 0.0
    assert not model_is_local("gpt-4o-mini")
    assert estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000) == 0.75
