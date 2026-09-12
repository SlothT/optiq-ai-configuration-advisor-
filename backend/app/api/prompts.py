from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import db_session, get_current_user, get_project_for_user
from app.models.domain import Prompt, User
from app.schemas.domain import PromptAnalyzeResponse
from app.services.phase1 import analyze_prompt, compose_prompt_with_context

router = APIRouter(prefix="/api/v1/prompts", tags=["prompts"])


@router.post("/analyze", response_model=PromptAnalyzeResponse)
async def analyze_prompt_route(
    project_id: str = Form(...),
    task_type: str = Form(...),
    judge_model: str = Form(...),
    text: str | None = Form(None),
    source_prompt_id: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
    file: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> dict:
    get_project_for_user(project_id, current_user, db)
    user_prompt = (text or "").strip()
    uploads = list(files or [])
    if file is not None:
        uploads.append(file)
    attachments: list[tuple[str | None, bytes]] = []
    for upload in uploads:
        attachments.append((upload.filename, await upload.read()))

    composed, context_text, context_meta = compose_prompt_with_context(user_prompt, attachments)
    if not user_prompt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter a user prompt. Uploaded files are used as context, not as the prompt.",
        )

    prompt, analysis = analyze_prompt(
        db,
        project_id=project_id,
        task_type=task_type,
        prompt_text=composed,
        judge_model=judge_model,
        source_prompt_id=source_prompt_id,
        user_prompt=user_prompt,
        context_text=context_text,
        context_meta=context_meta,
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
        "cost_is_local": bool(analysis.analysis_json.get("cost_is_local")),
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
