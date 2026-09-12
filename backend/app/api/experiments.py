from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import db_session, get_current_user, get_project_for_user
from app.models.domain import Experiment, Prompt, User
from app.schemas.domain import ExperimentEstimateRequest, ExperimentRunRequest, ExperimentSummary
from app.services.auto import expand_model_ids
from app.services.evaluation import parse_test_inputs
from app.services.phase1 import build_experiment_summary, estimate_experiment_cost
from app.workers.queue import enqueue_experiment

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])


def _load_prompts(db: Session, project_id: str, prompt_ids: list[str]) -> list[Prompt]:
    prompts = db.query(Prompt).filter(Prompt.project_id == project_id, Prompt.id.in_(prompt_ids)).all()
    if len(prompts) != len(prompt_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more prompts were not found")
    return prompts


@router.post("/estimate")
def estimate_experiment_route(
    request: ExperimentEstimateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> dict:
    get_project_for_user(request.project_id, current_user, db)
    if not request.prompt_ids or not request.model_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one prompt and one model are required")
    try:
        model_ids = expand_model_ids(db, request.project_id, request.model_ids)
        test_inputs = parse_test_inputs([item.model_dump() for item in request.test_inputs])
        estimate = estimate_experiment_cost(
            db,
            project_id=request.project_id,
            prompt_ids=request.prompt_ids,
            model_ids=model_ids,
            test_inputs=test_inputs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {
        "requires_confirmation": True,
        "resolved_model_ids": model_ids,
        **estimate,
        "message": "Confirm the cost estimate to queue the experiment",
    }


@router.post("/run")
def run_experiment_route(
    request: ExperimentRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> dict:
    get_project_for_user(request.project_id, current_user, db)
    if not request.prompt_ids or not request.model_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one prompt and one model are required")
    _load_prompts(db, request.project_id, request.prompt_ids)

    try:
        model_ids = expand_model_ids(db, request.project_id, request.model_ids)
        test_inputs = parse_test_inputs([item.model_dump() for item in request.test_inputs])
        estimate = estimate_experiment_cost(
            db,
            project_id=request.project_id,
            prompt_ids=request.prompt_ids,
            model_ids=model_ids,
            test_inputs=test_inputs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    if not request.confirm_cost:
        return {
            "requires_confirmation": True,
            "resolved_model_ids": model_ids,
            **estimate,
            "message": "Confirm the cost estimate to queue the experiment",
        }

    experiment = Experiment(
        project_id=request.project_id,
        status="queued",
        task_type=request.task_type,
        prompt_ids_json=request.prompt_ids,
        model_ids_json=model_ids,
        test_inputs_json=test_inputs,
        results_json={"label": request.label, "temperature": request.temperature or 0.2},
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)

    try:
        job_id = enqueue_experiment(experiment.id, request.temperature or 0.2)
        experiment.results_json = {**(experiment.results_json or {}), "rq_job_id": job_id}
        db.commit()
        db.refresh(experiment)
    except Exception as exc:
        experiment.status = "failed"
        experiment.results_json = {"error": f"Could not queue experiment: {exc}"}
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis/RQ worker is unavailable. Start Redis and the worker container, then retry.",
        ) from exc

    return build_experiment_summary(experiment)


@router.get("", response_model=list[ExperimentSummary])
def list_experiments(
    project_id: str,
    tag: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> list[dict]:
    get_project_for_user(project_id, current_user, db)
    query = db.query(Experiment).filter(Experiment.project_id == project_id).order_by(Experiment.created_at.desc())
    experiments = query.limit(max(1, min(limit, 200))).all()
    summaries = [build_experiment_summary(experiment) for experiment in experiments]
    if tag:
        summaries = [
            item
            for item in summaries
            if tag.lower() in str((item.get("results") or {}).get("label") or item.get("task_type") or "").lower()
        ]
    return summaries


@router.get("/compare")
def compare_experiments(
    ids: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> dict:
    experiment_ids = [item.strip() for item in ids.split(",") if item.strip()]
    experiments = db.query(Experiment).filter(Experiment.id.in_(experiment_ids)).all()
    if len(experiments) != len(experiment_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more experiments not found")
    for experiment in experiments:
        get_project_for_user(experiment.project_id, current_user, db)
    return {"experiments": [build_experiment_summary(experiment) for experiment in experiments]}


@router.get("/{experiment_id}", response_model=ExperimentSummary)
def get_experiment(
    experiment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> dict:
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).one_or_none()
    if not experiment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    get_project_for_user(experiment.project_id, current_user, db)
    return build_experiment_summary(experiment)


@router.get("/{experiment_id}/metrics")
def get_experiment_metrics(
    experiment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> dict:
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).one_or_none()
    if not experiment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    get_project_for_user(experiment.project_id, current_user, db)
    return experiment.results_json or {}
