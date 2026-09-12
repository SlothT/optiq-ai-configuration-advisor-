from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

import mlflow

from app.core.config import settings
from app.models.domain import Experiment

logger = logging.getLogger("optiq.mlflow")


def log_experiment_to_mlflow(
    experiment: Experiment,
    *,
    task_type: str,
    prompt_ids: list[str],
    model_ids: list[str],
    test_inputs: list[dict[str, Any]],
    results: dict[str, Any],
    temperature: float,
    prompts: list[Any],
    project_name: str | None = None,
) -> str | None:
    try:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment("Optiq")
        with mlflow.start_run(run_name=f"experiment-{experiment.id}") as run:
            mlflow.set_tags(
                {
                    "project_name": project_name or experiment.project_id,
                    "task_type": task_type,
                    "has_ground_truth": str(any(item.get("reference_answer") for item in test_inputs)),
                    "optiq_experiment_id": experiment.id,
                }
            )
            mlflow.log_params(
                {
                    "experiment_id": experiment.id,
                    "task_type": task_type,
                    "prompt_ids": ",".join(prompt_ids),
                    "model_ids": ",".join(model_ids),
                    "temperature": temperature,
                    "judge_models": ",".join(
                        str(getattr(prompt, "judge_model", "") or "") for prompt in prompts
                    ),
                }
            )
            summary = results.get("summary") or {}
            for key, value in summary.items():
                if isinstance(value, (int, float)) and value is not None:
                    mlflow.log_metric(key, float(value))

            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                (root / "test_inputs.json").write_text(json.dumps(test_inputs, indent=2), encoding="utf-8")
                (root / "evaluation_report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
                prompt_blob = [
                    {
                        "id": prompt.id,
                        "version": prompt.version,
                        "task_type": prompt.task_type,
                        "text": prompt.raw_text,
                    }
                    for prompt in prompts
                ]
                (root / "prompts.json").write_text(json.dumps(prompt_blob, indent=2), encoding="utf-8")
                outputs = [
                    {
                        "model_id": row.get("model_id"),
                        "prompt_id": row.get("prompt_id"),
                        "input_index": row.get("input_index"),
                        "raw_output": row.get("raw_output"),
                        "error": row.get("error"),
                    }
                    for row in results.get("rows") or []
                ]
                (root / "model_outputs.json").write_text(json.dumps(outputs, indent=2), encoding="utf-8")
                mlflow.log_artifacts(str(root))

            for model_summary in results.get("per_model") or []:
                model_id = str(model_summary.get("model_id") or "model")
                with mlflow.start_run(run_name=model_id, nested=True):
                    mlflow.set_tags(
                        {
                            "provider": str(model_summary.get("provider") or ""),
                            "prompt_id": str(model_summary.get("prompt_id") or ""),
                        }
                    )
                    mlflow.log_params(
                        {
                            "model": model_id,
                            "temperature": temperature,
                            "prompt_id": str(model_summary.get("prompt_id") or ""),
                        }
                    )
                    for key in (
                        "quality_score",
                        "accuracy",
                        "answer_relevancy",
                        "faithfulness",
                        "latency_p50_ms",
                        "latency_p95_ms",
                        "total_cost_usd",
                        "input_tokens",
                        "output_tokens",
                    ):
                        value = model_summary.get(key)
                        if isinstance(value, (int, float)) and value is not None:
                            mlflow.log_metric(key, float(value))
            return run.info.run_id
    except Exception as exc:
        logger.warning("mlflow logging failed for experiment %s: %s", experiment.id, exc)
        return None
