from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import db_session, get_current_user, get_project_for_user
from app.models.domain import Prompt, Project, User
from app.schemas.domain import PromptAnalyzeResponse
from app.services.phase1 import analyze_prompt, _resolve_prompt_text

router = APIRouter(prefix="/api/v1/prompts", tags=["prompts"])


@router.post("/analyze", response_model=PromptAnalyzeResponse)
async def analyze_prompt_route(
    project_id: str = Form(...),
    task_type: str = Form(...),
    judge_model: str = Form(...),
    text: str | None = Form(None),
    source_prompt_id: str | None = Form(None),
    file: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> dict:
    get_project_for_user(project_id, current_user, db)
    raw_bytes = await file.read() if file else b""
    prompt_text = _resolve_prompt_text(file.filename if file else None, raw_bytes, text)
    if not prompt_text.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Prompt text or file content is required")

    prompt, analysis = analyze_prompt(
        db,
        project_id=project_id,
        task_type=task_type,
        prompt_text=prompt_text,
        judge_model=judge_model,
        source_prompt_id=source_prompt_id,
    )
    db.commit()
    db.refresh(prompt)
    return {
        "prompt_id": prompt.id,
        "version": prompt.version,
        "quality_score": analysis.quality_score,
        "strengths": analysis.strengths,
        "weaknesses": analysis.weaknesses,
        "suggested_improvements": analysis.suggested_improvements,
        "estimated_tokens": analysis.estimated_tokens,
        "estimated_cost_usd": analysis.estimated_cost_usd,
        "judge_model": analysis.judge_model,
        "analysis_json": analysis.analysis_json,
    }


@router.get("", response_model=list[dict])
def list_prompts(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> list[dict]:
    get_project_for_user(project_id, current_user, db)
    prompts = db.query(Prompt).filter(Prompt.project_id == project_id).order_by(Prompt.version.desc()).all()
    return [
        {
            "id": prompt.id,
            "project_id": prompt.project_id,
            "source_prompt_id": prompt.source_prompt_id,
            "version": prompt.version,
            "raw_text": prompt.raw_text,
            "task_type": prompt.task_type,
            "quality_score": prompt.quality_score,
            "estimated_tokens": prompt.estimated_tokens,
            "estimated_cost_usd": prompt.estimated_cost_usd,
            "judge_model": prompt.judge_model,
            "analysis_json": prompt.analysis_json,
            "created_at": prompt.created_at.isoformat() if prompt.created_at else None,
        }
        for prompt in prompts
    ]
