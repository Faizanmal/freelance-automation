from __future__ import annotations

from typing import Annotated

from app.core.security.rate_limit import auth_rate_limiter, client_ip
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.core.session import get_db
from database.models.roadmap import RoadmapVote
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

router = APIRouter(prefix="/roadmap", tags=["roadmap"])

ROADMAP_ITEMS: list[dict[str, str]] = [
    {
        "key": "ai-proposals",
        "title": "AI Proposal Generation",
        "description": "Auto-generate cover letters tailored to the client's job description.",
        "status": "In Progress",
    },
    {
        "key": "mobile-app",
        "title": "Mobile App (iOS & Android)",
        "description": "A native app for job-alert push notifications.",
        "status": "Planned",
    },
    {
        "key": "linkedin",
        "title": "LinkedIn Integration",
        "description": "Pull freelance and contract posts from LinkedIn.",
        "status": "Under Review",
    },
    {
        "key": "theme-sync",
        "title": "Dark/Light Mode Sync",
        "description": "Keep the theme preference in the account, not only on this browser.",
        "status": "Completed",
    },
]

_KEYS = {item["key"] for item in ROADMAP_ITEMS}


class RoadmapItemOut(BaseModel):
    key: str
    title: str
    description: str
    status: str
    votes: int
    voted: bool


class RoadmapVoteIn(BaseModel):
    feature_key: str = Field(min_length=1, max_length=64)
    voter_id: str = Field(min_length=8, max_length=64)


@router.get("", response_model=list[RoadmapItemOut])
async def list_roadmap(
    session: Annotated[AsyncSession, Depends(get_db)],
    voter_id: str | None = Query(None, max_length=64),
) -> list[RoadmapItemOut]:
    count_rows = (
        await session.execute(
            select(RoadmapVote.feature_key, func.count()).group_by(
                RoadmapVote.feature_key
            )
        )
    ).all()
    counts = {feature_key: int(count) for feature_key, count in count_rows}
    voted_keys: set[str] = set()
    if voter_id:
        rows = await session.execute(
            select(RoadmapVote.feature_key).where(RoadmapVote.voter_id == voter_id)
        )
        voted_keys = {row[0] for row in rows.all()}
    return [
        RoadmapItemOut(
            key=item["key"],
            title=item["title"],
            description=item["description"],
            status=item["status"],
            votes=counts.get(item["key"], 0),
            voted=item["key"] in voted_keys,
        )
        for item in ROADMAP_ITEMS
    ]


@router.post("/votes", response_model=RoadmapItemOut, status_code=status.HTTP_200_OK)
async def vote_roadmap(
    request: Request,
    payload: RoadmapVoteIn,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RoadmapItemOut:
    await auth_rate_limiter.check(
        f"roadmap:{client_ip(request)}", limit=30, window_seconds=3600
    )
    if payload.feature_key not in _KEYS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown roadmap item"
        )

    existing = await session.execute(
        select(RoadmapVote).where(
            RoadmapVote.feature_key == payload.feature_key,
            RoadmapVote.voter_id == payload.voter_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        session.add(
            RoadmapVote(feature_key=payload.feature_key, voter_id=payload.voter_id)
        )
        await session.commit()

    count = await session.scalar(
        select(func.count())
        .select_from(RoadmapVote)
        .where(RoadmapVote.feature_key == payload.feature_key)
    )
    item = next(entry for entry in ROADMAP_ITEMS if entry["key"] == payload.feature_key)
    return RoadmapItemOut(
        key=item["key"],
        title=item["title"],
        description=item["description"],
        status=item["status"],
        votes=int(count or 0),
        voted=True,
    )
