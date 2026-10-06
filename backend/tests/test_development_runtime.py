from __future__ import annotations

import re
import time
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.adapters.base import GenerateResult
from app.core.config import Settings, settings
from app.core.database import Base
from app.core.deps import db_session
from app.main import app
from app.mlflow_integration import log_experiment_to_mlflow
from app.workers import experiments, queue


def test_database_configuration_is_required(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


def test_cors_only_allows_configured_origins() -> None:
    from app.main import allowed_origins

    configured = {origin.rstrip("/") for origin in settings.cors_origins}
    configured.add(settings.frontend_url.rstrip("/"))
    with TestClient(app) as client:
        for origin in [settings.frontend_url, "http://127.0.0.1:3001", "https://unconfigured.example"]:
            if not origin:
                continue
            response = client.options("/api/v1/health", headers={
                "Origin": origin, "Access-Control-Request-Method": "GET",
            })
            assert response.status_code == (200 if origin in configured else 400)
    assert allowed_origins == configured


@pytest.mark.parametrize("backend", [{"mail_backend": "file"}, {"job_backend": "thread"}])
def test_local_backends_require_development_mode(backend: dict) -> None:
    with pytest.raises(ValidationError, match="require DEBUG=true"):
        Settings(_env_file=None, debug=False, **backend)


def test_disabled_tracking_does_not_import_mlflow(monkeypatch) -> None:
    import builtins

    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name == "mlflow":
            raise AssertionError("Disabled tracking must not require MLflow")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(settings, "mlflow_tracking_uri", "")
    monkeypatch.setattr(builtins, "__import__", guarded)
    assert log_experiment_to_mlflow(
        None, task_type="classification", prompt_ids=[], model_ids=[], test_inputs=[],
        results={}, temperature=0, prompts=[],
    ) is None


def test_rq_failure_does_not_start_local_threads(monkeypatch) -> None:
    monkeypatch.setattr(settings, "job_backend", "rq")

    def unavailable():
        raise ConnectionError("Redis offline")

    monkeypatch.setattr(queue, "experiment_queue", unavailable)
    with pytest.raises(ConnectionError, match="Redis offline"):
        queue.enqueue_experiment("missing", 0)


@pytest.fixture
def native_client(tmp_path: Path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    def db_override():
        with sessions() as db:
            yield db

    from app.core.rate_limit import _local

    _local.clear()
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "job_backend", "thread")
    monkeypatch.setattr(settings, "mail_backend", "file")
    monkeypatch.setattr(settings, "mail_directory", tmp_path / "mail")
    monkeypatch.setattr(settings, "mlflow_tracking_uri", "")
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    monkeypatch.setattr(experiments, "SessionLocal", sessions)
    app.dependency_overrides[db_session] = db_override
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_failed_resend_preserves_existing_verification_link(native_client, monkeypatch) -> None:
    email = "resend-test@example.com"
    registration = native_client.post("/api/v1/auth/register", json={"email": email, "password": "letters123"})
    assert registration.status_code == 201
    message = next(settings.mail_directory.glob("*.eml")).read_text()
    token = re.search(r"token=([A-Za-z0-9_-]+)", message).group(1)
    monkeypatch.setattr("app.api.auth._deliver_verification", lambda *_args: False)
    response = native_client.post("/api/v1/auth/resend-verification", json={"email": email})
    assert response.status_code == 503
    assert native_client.post("/api/v1/auth/verify", json={"token": token}).status_code == 200


def test_native_signup_analysis_and_background_experiment(native_client, monkeypatch) -> None:
    client = native_client
    registration = client.post("/api/v1/auth/register", json={"email": "contributor@example.com", "password": "letters123"})
    assert registration.status_code == 201
    assert "verification email saved in MAIL_DIRECTORY" in registration.json()["message"]
    assert client.post("/api/v1/auth/login", json={
        "email": "contributor@example.com", "password": "letters123",
    }).status_code == 403
    email = next(settings.mail_directory.glob("*.eml"))
    assert email.stat().st_mode & 0o777 == 0o600
    verification_token = re.search(r"token=([A-Za-z0-9_-]+)", email.read_text()).group(1)
    verified = client.post("/api/v1/auth/verify", json={"token": verification_token})
    assert verified.status_code == 200
    assert client.post("/api/v1/auth/verify", json={"token": verification_token}).status_code == 400
    headers = {"Authorization": f"Bearer {verified.json()['access_token']}"}
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Native smoke test"}).json()
    project_id = project["id"]
    saved = client.post(f"/api/v1/projects/{project_id}/providers", headers=headers,
                        json={"provider_name": "openai", "api_key": "test-only-key"})
    assert saved.status_code == 200
    assert saved.json()["has_api_key"] is True
    assert "test-only-key" not in saved.text

    generation_requests = []

    class StubAdapter:
        provider_name = "openai"

        def generate(self, **kwargs):
            generation_requests.append(kwargs)
            return GenerateResult(text="4", input_tokens=10, output_tokens=1)

        def embed(self, _texts):
            return None

        def estimate_cost(self, *_args):
            return 0.00001

    from app.services import phase1

    monkeypatch.setattr(phase1.AdapterFactory, "from_resolution", lambda _resolution: StubAdapter())
    monkeypatch.setattr(phase1, "estimate_tokens", lambda text, _model=None: max(1, len(text) // 4))
    monkeypatch.setattr("app.services.evaluation.try_ragas_metrics", lambda *_args: None)
    analysis = client.post("/api/v1/prompts/analyze", headers=headers, data={
        "project_id": project_id, "text": "Classify this arithmetic result. Return only the number.",
        "task_type": "classification", "judge_model": "gpt-4o-mini",
    })
    assert analysis.status_code == 200
    assert generation_requests == []  # Saving/reviewing a prompt does not spend credits.
    payload = {
        "project_id": project_id, "prompt_ids": [analysis.json()["prompt_id"]],
        "model_ids": ["gpt-4o-mini"], "task_type": "classification", "temperature": 0, "max_output_tokens": 64,
        "test_inputs": [{"input": "2+2", "reference_answer": "4"}],
    }
    estimated = client.post("/api/v1/experiments/run", headers=headers, json=payload)
    assert estimated.json()["requires_confirmation"] is True
    assert client.get(f"/api/v1/experiments?project_id={project_id}", headers=headers).json() == []
    underfunded = client.post("/api/v1/experiments/run", headers=headers, json=payload | {"confirm_cost": True, "budget_usd": 0})
    assert underfunded.status_code == 422
    assert client.get(f"/api/v1/experiments?project_id={project_id}", headers=headers).json() == []
    started = client.post("/api/v1/experiments/run", headers=headers, json=payload | {"confirm_cost": True})
    assert started.status_code == 200
    experiment_id = started.json()["id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = client.get(f"/api/v1/experiments/{experiment_id}", headers=headers).json()
        if result["status"] in {"completed", "failed"}:
            break
        time.sleep(0.01)
    assert result["status"] == "completed", result
    assert result["results"]["rq_job_id"] == "inline"
    assert result["results"]["temperature"] == 0
    assert result["results"]["rows"][0]["accuracy"] == 100
    assert len(generation_requests) == 1
    assert generation_requests[0]["max_tokens"] == 64
    assert "Reference Answer" not in generation_requests[0]["prompt"]
    assert "Input: 2+2" in generation_requests[0]["prompt"]
    assert experiments.execute_experiment_job(experiment_id)["status"] == "already_claimed"
    assert len(generation_requests) == 1
    recommendation = client.post("/api/v1/recommendations/model", headers=headers, json={
        "project_id": project_id, "experiment_id": experiment_id, "goal": "highest_quality",
    })
    assert recommendation.status_code == 200
    assert recommendation.json()["recommended_config"]["model_id"] == "gpt-4o-mini"
    for constraint in [{"max_cost": 0}, {"max_latency_ms": 0}, {"requires_structured_json": True}]:
        rejected = client.post("/api/v1/recommendations/model", headers=headers, json={
            "project_id": project_id, "experiment_id": experiment_id, **constraint,
        })
        assert rejected.status_code == 200
        assert rejected.json()["recommended_config"]["model_id"] is None
        assert rejected.json()["excluded_options"]
    feedback = client.post(f"/api/v1/experiments/{experiment_id}/feedback", headers=headers,
                           json={"row_index": 0, "accepted": True})
    assert feedback.status_code == 200
    assert feedback.json()["results"]["user_feedback"]["0"]["scope"] == "observed_output_only"
    assert client.post(f"/api/v1/experiments/{experiment_id}/feedback", headers=headers,
                       json={"row_index": 99, "accepted": True}).status_code == 422
    other_project = client.post("/api/v1/projects", headers=headers, json={"name": "Other project"}).json()
    assert client.post("/api/v1/recommendations/model", headers=headers, json={
        "project_id": other_project["id"], "experiment_id": experiment_id,
    }).status_code == 422


def test_token_estimates_work_without_downloaded_tokenizer_data(monkeypatch) -> None:
    from app.services import phase1

    def unavailable(*_args):
        raise ConnectionError("Tokenizer data unavailable offline")

    monkeypatch.setattr(phase1.tiktoken, "encoding_for_model", unavailable)
    monkeypatch.setattr(phase1.tiktoken, "get_encoding", unavailable)
    assert phase1.estimate_tokens("Hello world") == 3
    assert phase1.estimate_tokens("") == 0


def test_login_rate_limit_and_generic_error(native_client) -> None:
    payload = {"email": "missing@example.com", "password": "letters123"}
    for _ in range(10):
        response = native_client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 401
        assert response.json()["detail"] == "Email or password is incorrect."
    response = native_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_feedback_validation_persistence_and_limit(native_client) -> None:
    from app.models.domain import ProductFeedback

    payload = {"page": "/advisor", "rating": "helpful", "comment": " Easier to compare "}
    assert native_client.post("/api/v1/feedback", json={**payload, "page": "/auth/verify?token=secret"}).status_code == 422
    assert native_client.post("/api/v1/feedback", json={**payload, "comment": "x" * 1001}).status_code == 422
    for _ in range(10):
        assert native_client.post("/api/v1/feedback", json=payload).status_code == 201
    assert native_client.post("/api/v1/feedback", json=payload).status_code == 429
    override = app.dependency_overrides[db_session]()
    db = next(override)
    assert db.query(ProductFeedback).count() == 10
    assert db.query(ProductFeedback).first().comment == "Easier to compare"
    override.close()
    assert native_client.get("/api/v1/feedback").status_code == 405


def test_brevo_uses_https_and_verified_sender(monkeypatch) -> None:
    from app.services import email

    monkeypatch.setattr(settings, "mail_backend", "smtp")
    monkeypatch.setattr(settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(settings, "smtp_from", "Optiq <owner@example.com>")
    requests = []

    def post(url, **kwargs):
        requests.append((url, kwargs))
        return __import__("httpx").Response(201, request=__import__("httpx").Request("POST", url))

    monkeypatch.setattr(email.httpx, "post", post)
    assert email.send_verification_email("user@example.com", "https://app.example/auth/verify?token=test")
    url, args = requests[0]
    assert url == "https://api.brevo.com/v3/smtp/email"
    assert args["json"]["sender"] == {"name": "Optiq", "email": "owner@example.com"}
    assert args["json"]["to"] == [{"email": "user@example.com"}]


def test_production_configuration_requires_secure_settings() -> None:
    valid = dict(app_env="production", debug=False, job_backend="rq", mail_backend="smtp",
                 database_url="postgresql://test:test@db.example/optiq?sslmode=require",
                 redis_url="redis://queue:6379", jwt_secret="a" * 40,
                 fernet_key=Fernet.generate_key().decode(), frontend_url="https://app.example",
                 smtp_from="Optiq <owner@example.com>", brevo_api_key="test-key", cors_origins=[])
    assert Settings(_env_file=None, **valid).database_url.startswith("postgresql+psycopg2://")
    for invalid in [{"debug": True}, {"database_url": "sqlite:///test.db"}, {"jwt_secret": "short"},
                    {"fernet_key": "bad"}, {"frontend_url": "http://localhost:3000"},
                    {"smtp_from": "Optiq <noreply@optiq.local>"}, {"redis_url": ""}]:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **{**valid, **invalid})


def test_shared_rate_limit_fails_closed(monkeypatch) -> None:
    from fastapi import HTTPException
    from redis.exceptions import ConnectionError

    from app.core import rate_limit

    monkeypatch.setattr(settings, "app_env", "production")

    def unavailable(*args, **kwargs):
        raise ConnectionError("unavailable")

    monkeypatch.setattr(rate_limit.Redis, "from_url", unavailable)
    with pytest.raises(HTTPException) as error:
        rate_limit._increment("test", 60)
    assert error.value.status_code == 503


def test_google_cannot_activate_an_unverified_password(native_client, monkeypatch) -> None:
    import httpx

    from app.api import auth

    email = "google-owner@example.com"
    assert native_client.post("/api/v1/auth/register", json={"email": email, "password": "attacker123"}).status_code == 201
    old_token = re.search(r"token=([\w-]+)", next(settings.mail_directory.glob("*.eml")).read_text()).group(1)
    monkeypatch.setattr(settings, "google_client_id", "test-client")
    monkeypatch.setattr(auth.httpx, "get", lambda *args, **kwargs: httpx.Response(
        200, json={"aud": "test-client", "email_verified": "true", "email": email},
        request=httpx.Request("GET", "https://oauth2.googleapis.com/tokeninfo"),
    ))
    response = native_client.post("/api/v1/auth/google", json={"id_token": "fixture"})
    assert response.status_code == 200
    assert native_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + response.json()["access_token"]}).status_code == 200
    assert native_client.post("/api/v1/auth/login", json={"email": email, "password": "attacker123"}).status_code == 401
    assert native_client.post("/api/v1/auth/verify", json={"token": old_token}).status_code == 400


def test_embedded_runtime_stops_api_when_worker_exits(monkeypatch) -> None:
    from app import runtime

    monkeypatch.setattr(settings, "embedded_worker", True)
    monkeypatch.setattr(settings, "job_backend", "rq")
    monkeypatch.setattr(runtime.signal, "signal", lambda *args: None)
    children = []

    class Child:
        def __init__(self, command):
            self.command = command
            self.exit_code = 1 if not children else None
            self.terminated = False
            children.append(self)

        def poll(self):
            return self.exit_code

        def terminate(self):
            self.terminated = True
            self.exit_code = -15

        def wait(self, timeout=None):
            return self.exit_code

    monkeypatch.setattr(runtime.subprocess, "Popen", Child)
    assert runtime.main() == 1
    assert children[1].terminated
    assert settings.redis_url not in children[0].command


def test_simultaneous_verification_consumes_token_once(native_client) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy import event

    assert native_client.post("/api/v1/auth/register", json={
        "email": "race@example.com", "password": "letters123",
    }).status_code == 201
    token = re.search(r"token=([\w-]+)", next(settings.mail_directory.glob("*.eml")).read_text()).group(1)
    override = app.dependency_overrides[db_session]()
    engine = next(override).get_bind()
    override.close()
    barrier = Barrier(2)

    def both_read_token(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT") and "WHERE users.email_verify_token_hash =" in statement:
            barrier.wait(timeout=5)

    event.listen(engine, "after_cursor_execute", both_read_token)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: native_client.post("/api/v1/auth/verify", json={"token": token}), range(2)))
        assert sorted(response.status_code for response in results) == [200, 400]
    finally:
        event.remove(engine, "after_cursor_execute", both_read_token)
