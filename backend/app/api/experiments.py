from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import db_session, get_current_user, get_project_for_user
from app.models.domain import Experiment, Prompt, Project, User
from app.schemas.domain import ExperimentRunRequest, ExperimentSummary
from app.services.phase1 import build_experiment_summary, log_experiment_to_mlflow, run_experiment

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])


@router.post("/run", response_model=dict)
def run_experiment_route(
    request: ExperimentRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> dict:
    get_project_for_user(request.project_id, current_user, db)
    if not request.prompt_ids or not request.model_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one prompt and one model are required")

    prompts = db.query(Prompt).filter(Prompt.project_id == request.project_id, Prompt.id.in_(request.prompt_ids)).all()
    if len(prompts) != len(request.prompt_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more prompts were not found")

    if not request.confirm_cost:
        estimated_rows = max(len(request.test_inputs) or 1, 1) * len(request.prompt_ids) * len(request.model_ids)
        estimated_cost = 0.0
        for model_id in request.model_ids:
            prompt = prompts[0]
            estimated_cost += (prompt.estimated_cost_usd or 0.0) * max(len(request.test_inputs), 1)
        return {
            "requires_confirmation": True,
            "estimated_cost_usd": round(estimated_cost, 6),
            "estimated_rows": estimated_rows,
            "message": "Confirm the cost estimate to execute the experiment",
        }

    experiment = Experiment(
        project_id=request.project_id,
        status="running",
        task_type=request.task_type,
        prompt_ids_json=request.prompt_ids,
        model_ids_json=request.model_ids,
        test_inputs_json=[item.model_dump() for item in request.test_inputs],
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)

    try:
        result = run_experiment(
            db,
            project_id=request.project_id,
            prompt_ids=request.prompt_ids,
            model_ids=request.model_ids,
            task_type=request.task_type,
            test_inputs=[item.model_dump() for item in request.test_inputs],
            temperature=request.temperature or 0.2,
        )
        experiment.results_json = {"rows": result.rows, "summary": result.summary}
        experiment.status = "completed"
        experiment.mlflow_run_id = log_experiment_to_mlflow(
            experiment,
            task_type=request.task_type,
            prompt_ids=request.prompt_ids,
            model_ids=request.model_ids,
            test_inputs=[item.model_dump() for item in request.test_inputs],
            results=experiment.results_json,
        )
        db.commit()
        db.refresh(experiment)
    except Exception as exc:
        experiment.status = "failed"
        experiment.results_json = {"error": str(exc)}
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return build_experiment_summary(experiment)


@router.get("", response_model=list[ExperimentSummary])
def list_experiments(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> list[dict]:
    get_project_for_user(project_id, current_user, db)
    experiments = db.query(Experiment).filter(Experiment.project_id == project_id).order_by(Experiment.created_at.desc()).all()
    return [build_experiment_summary(experiment) for experiment in experiments]


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
