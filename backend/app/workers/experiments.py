from __future__ import annotations

import logging

from app.core.database import SessionLocal
from app.mlflow_integration import log_experiment_to_mlflow
from app.models.domain import Experiment, Project
from app.services.phase1 import run_experiment

logger = logging.getLogger("optiq.worker")


def execute_experiment_job(experiment_id: str, temperature: float = 0.2) -> dict:
    db = SessionLocal()
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).one_or_none()
    if not experiment:
        db.close()
        raise ValueError(f"Experiment {experiment_id} not found")

    experiment.status = "running"
    db.commit()
    logger.info("experiment %s running models=%s", experiment.id, experiment.model_ids_json)

    try:
        result = run_experiment(
            db,
            project_id=experiment.project_id,
            prompt_ids=list(experiment.prompt_ids_json or []),
            model_ids=list(experiment.model_ids_json or []),
            task_type=experiment.task_type,
            test_inputs=list(experiment.test_inputs_json or []),
            temperature=temperature,
        )
        previous = experiment.results_json or {}
        experiment.results_json = {
            "rows": result.rows,
            "summary": result.summary,
            "per_model": result.summary.get("per_model"),
            "temperature": temperature,
            "label": previous.get("label"),
            "rq_job_id": previous.get("rq_job_id"),
        }
        prompts = result.prompts
        project = db.query(Project).filter(Project.id == experiment.project_id).one_or_none()
        experiment.mlflow_run_id = log_experiment_to_mlflow(
            experiment,
            task_type=experiment.task_type,
            prompt_ids=list(experiment.prompt_ids_json or []),
            model_ids=list(experiment.model_ids_json or []),
            test_inputs=list(experiment.test_inputs_json or []),
            results=experiment.results_json,
            temperature=temperature,
            prompts=prompts,
            project_name=project.name if project else None,
        )
        experiment.status = "completed"
        db.commit()
        logger.info("experiment %s completed mlflow=%s", experiment.id, experiment.mlflow_run_id)
        return {"status": "completed", "experiment_id": experiment.id}
    except Exception as exc:
        logger.exception("experiment %s failed: %s", experiment_id, exc)
        experiment.status = "failed"
        experiment.results_json = {"error": str(exc)}
        db.commit()
        raise
    finally:
        db.close()
