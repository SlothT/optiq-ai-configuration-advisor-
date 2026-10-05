from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.services.advisor import advise

router = APIRouter(prefix="/api/v1/advice", tags=["advice"])


class AdviceRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)
    preference: Literal["cost", "balanced", "quality"] = "cost"
    expected_output_tokens: int = Field(default=1024, ge=1, le=4096)
    baseline_model_id: str | None = None
    allowed_providers: list[Literal["openai", "anthropic", "google", "ollama"]] = Field(default_factory=list)
    local_only: bool = False
    max_cost_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator("prompt")
    @classmethod
    def nonempty_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a prompt")
        return value.strip()


@router.post("")
def prompt_advice(request: AdviceRequest) -> dict:
    # Public, deterministic, and independent of provider credentials or projects.
    return advise(request.model_dump())
