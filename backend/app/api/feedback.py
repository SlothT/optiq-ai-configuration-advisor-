from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import db_session
from app.core.rate_limit import check_rate_limit
from app.models.domain import ProductFeedback

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    page: str = Field(max_length=100, pattern=r"^/[a-zA-Z0-9/_-]*$")
    rating: Literal["helpful", "not_helpful"]
    comment: str = Field(default="", max_length=1000)


@router.post("", status_code=201)
def submit_feedback(payload: FeedbackRequest, request: Request, db: Session = Depends(db_session)) -> dict:
    check_rate_limit(request, limit=10, window=3600)
    db.add(ProductFeedback(page=payload.page, rating=payload.rating, comment=payload.comment.strip()))
    db.commit()
    return {"message": "Thanks for your feedback."}
