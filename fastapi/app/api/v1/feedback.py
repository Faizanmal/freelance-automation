from __future__ import annotations

from typing import Annotated, Literal

from app.core.security.rate_limit import auth_rate_limiter, client_ip
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database.core.session import get_db
from database.models.roadmap import CancellationFeedback
from fastapi import APIRouter, Depends, Request, status

router = APIRouter(prefix="/feedback", tags=["feedback"])

CancellationReason = Literal[
    "too_expensive", "missing_features", "not_enough_jobs", "switching", "other"
]


class CancellationFeedbackIn(BaseModel):
    reason: CancellationReason
    details: str | None = Field(None, max_length=2000)
    email: str | None = Field(None, max_length=256)


@router.post("/cancellation", status_code=status.HTTP_202_ACCEPTED)
async def submit_cancellation_feedback(
    request: Request,
    payload: CancellationFeedbackIn,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    await auth_rate_limiter.check(
        f"feedback:{client_ip(request)}", limit=10, window_seconds=3600
    )
    session.add(
        CancellationFeedback(
            email=(payload.email or "").strip() or None,
            reason=payload.reason,
            details=(payload.details or "").strip() or None,
        )
    )
    await session.commit()
    return {"detail": "Thanks. Your feedback was saved."}
