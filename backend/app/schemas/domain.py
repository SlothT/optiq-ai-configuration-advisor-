from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    email_verified: bool = False
    created_at: datetime | None = None


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        try:
            result = validate_email(value, check_deliverability=False)
        except EmailNotValidError as exc:
            raise ValueError("Enter a valid email address") from exc
        return str(result.normalized).lower()


class RegisterResponse(BaseModel):
    id: str
    email: str
    email_verified: bool
    message: str


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        try:
            result = validate_email(value, check_deliverability=False)
        except EmailNotValidError as orig:
            raise ValueError("Enter a valid email address") from orig
        return str(result.normalized).lower()


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        try:
            result = validate_email(value, check_deliverability=False)
        except EmailNotValidError as orig:
            raise ValueError("Enter a valid email address") from orig
        return str(result.normalized).lower()


class GoogleAuthRequest(BaseModel):
    id_token: str


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    created_at: datetime | None = None


class ProviderUpsertRequest(BaseModel):
    provider_name: str
    api_key: str | None = None
    ollama_base_url: str | None = None


class ProviderView(BaseModel):
    provider_name: str
    configured: bool
    has_api_key: bool = False
    ollama_base_url: str | None = None
    available_models: list[dict[str, Any]] = Field(default_factory=list)
    status_message: str | None = None


class PromptAnalyzeResponse(BaseModel):
    prompt_id: str
    version: int
    quality_score: float
    strengths: list[str]
    weaknesses: list[str]
    suggested_improvements: list[str]
    estimated_tokens: int
    estimated_cost_usd: float
    cost_is_local: bool = False
    judge_model: str | None = None
    analysis_json: dict[str, Any]


class ExperimentTestInput(BaseModel):
    input: str
    reference_answer: str | None = None
    context: str | None = None


class ExperimentEstimateRequest(BaseModel):
    project_id: str
    prompt_ids: list[str]
    model_ids: list[str]
    test_inputs: list[ExperimentTestInput] = Field(default_factory=list)


class ExperimentRunRequest(BaseModel):
    project_id: str
    prompt_ids: list[str]
    model_ids: list[str]
    task_type: str
    test_inputs: list[ExperimentTestInput] = Field(default_factory=list)
    confirm_cost: bool = False
    temperature: float | None = None
    label: str | None = None


class ExperimentRow(BaseModel):
    model_id: str
    prompt_id: str
    input_index: int
    raw_output: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    quality_score: float | None = None
    accuracy: float | None = None
    answer_relevancy: float | None = None
    faithfulness: float | None = None
    error: str | None = None


class ExperimentSummary(BaseModel):
    id: str
    project_id: str
    status: str
    task_type: str
    prompt_ids: list[str]
    model_ids: list[str]
    mlflow_run_id: str | None = None
    test_inputs: list[dict[str, Any]] | None = None
    results: dict[str, Any] | None = None
    created_at: datetime | None = None


class RecommendationRequest(BaseModel):
    project_id: str
    experiment_id: str | None = None
    goal: Literal["cheapest", "fastest", "highest_quality", "custom"] = "custom"
    max_cost: float | None = None
    max_latency_ms: float | None = None
    min_quality_score: float | None = None
    requires_structured_json: bool = False
    weights: dict[str, float] = Field(default_factory=dict)


class RecommendationResponse(BaseModel):
    id: str
    project_id: str
    experiment_id: str | None = None
    recommended_config: dict[str, Any]
    ranked_options: list[dict[str, Any]]
    excluded_options: list[dict[str, Any]]
    justification: str
