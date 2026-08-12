from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import db_session, get_current_user, get_project_for_user
from app.models.domain import Experiment, Recommendation, User
from app.schemas.domain import RecommendationRequest, RecommendationResponse
from app.services.phase1 import persist_recommendation, score_recommendations

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])


@router.post("/model", response_model=RecommendationResponse)
def recommend_model(
    request: RecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> dict:
    get_project_for_user(request.project_id, current_user, db)

    if request.experiment_id:
        experiment = db.query(Experiment).filter(Experiment.id == request.experiment_id).one_or_none()
        if not experiment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
        get_project_for_user(experiment.project_id, current_user, db)
        results = experiment.results_json or {}
    else:
        experiments = (
            db.query(Experiment)
            .filter(Experiment.project_id == request.project_id, Experiment.status == "completed")
            .order_by(Experiment.created_at.desc())
            .limit(1)
            .all()
        )
        if not experiments:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No completed experiment available")
        experiment = experiments[0]
        results = experiment.results_json or {}

    rows = results.get("rows") or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Experiment has no result rows")

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["model_id"], row["prompt_id"])].append(row)

    options: list[dict] = []
    for (model_id, prompt_id), group_rows in grouped.items():
        quality_values = [row.get("quality_score") or 0.0 for row in group_rows]
        cost_values = [row.get("cost_usd") or 0.0 for row in group_rows]
        latency_values = [row.get("latency_ms") or 0.0 for row in group_rows]
        option = {
            "model_id": model_id,
            "prompt_id": prompt_id,
            "quality_score": round(sum(quality_values) / len(quality_values), 2),
            "cost_usd": round(sum(cost_values) / len(cost_values), 6),
            "latency_ms": round(sum(latency_values) / len(latency_values), 2),
            "structured_output": any(str(row.get("raw_output", "")).strip().startswith("{") for row in group_rows),
        }
        options.append(option)

    ranked, excluded, top, justification = score_recommendations(
        options,
        {
            "goal": request.goal,
            "max_cost": request.max_cost,
            "max_latency_ms": request.max_latency_ms,
            "min_quality_score": request.min_quality_score,
            "requires_structured_json": request.requires_structured_json,
            "weights": request.weights,
        },
    )
    recommendation = persist_recommendation(
        db,
        project_id=request.project_id,
        experiment_id=experiment.id,
        request_payload=request.model_dump(),
        recommended_config=top,
        excluded_options=excluded,
        ranked_options=ranked,
        justification=justification,
    )
    db.commit()
    return {
        "id": recommendation.id,
        "project_id": recommendation.project_id,
        "experiment_id": recommendation.experiment_id,
        "recommended_config": recommendation.recommended_config,
        "ranked_options": recommendation.ranked_options,
        "excluded_options": recommendation.excluded_options,
        "justification": recommendation.justification,
    }
