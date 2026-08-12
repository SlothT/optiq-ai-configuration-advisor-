from app.config.model_registry import get_model, list_models, list_providers


def test_list_providers_includes_openai_and_ollama() -> None:
    providers = list_providers()
    assert "openai" in providers
    assert "ollama" in providers


def test_list_models_returns_enabled_models_only() -> None:
    models = list_models()
    model_ids = {model.id for model in models}
    assert "gpt-4o" in model_ids
    assert "llama3.2" in model_ids
    assert "claude-sonnet-4-20250514" not in model_ids


def test_get_model_returns_none_for_disabled() -> None:
    assert get_model("claude-sonnet-4-20250514") is None


def test_get_model_returns_openai_model() -> None:
    model = get_model("gpt-4o")
    assert model is not None
    assert model.provider == "openai"
    assert model.pricing is not None
    assert model.pricing.input_per_1m == 2.50
