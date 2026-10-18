"""Reddit hiring hunt — official API, [Hiring] posts only (skip [For Hire])."""

from __future__ import annotations

import base64
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.logging.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
OAUTH_BASE = "https://oauth.reddit.com"

HIRING_RE = re.compile(r"\[hiring\]", re.IGNORECASE)
FOR_HIRE_RE = re.compile(r"\[for\s*hire\]", re.IGNORECASE)


class SourceNotConfiguredError(RuntimeError):
    """Raised when Reddit API credentials are missing."""


def reddit_configured() -> bool:
    settings = get_settings()
    return bool(settings.reddit_client_id and settings.reddit_client_secret)


def is_hiring_post(title: str) -> bool:
    text = title or ""
    if FOR_HIRE_RE.search(text):
        return False
    return bool(HIRING_RE.search(text))


def _parse_subreddits(raw: str | None) -> list[str]:
    parts = [
        part.strip().lstrip("r/") for part in (raw or "").split(",") if part.strip()
    ]
    return parts or ["forhire", "hiring"]


async def _access_token(client: httpx.AsyncClient) -> str:
    settings = get_settings()
    client_id = (settings.reddit_client_id or "").strip()
    client_secret = (settings.reddit_client_secret or "").strip()
    if not client_id or not client_secret:
        raise SourceNotConfiguredError(
            "Reddit is not configured. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET."
        )
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    response = await client.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials"},
        headers={
            "Authorization": f"Basic {basic}",
            "User-Agent": settings.reddit_user_agent,
        },
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Reddit token response missing access_token")
    return str(token)


def _row_from_post(post: dict[str, Any], *, subreddit: str) -> dict[str, Any] | None:
    data = post.get("data") if isinstance(post, dict) else None
    if not isinstance(data, dict):
        return None
    title = str(data.get("title") or "").strip()
    if not title or not is_hiring_post(title):
        return None
    post_id = str(data.get("id") or "").strip()
    permalink = str(data.get("permalink") or "").strip()
    if not post_id or not permalink:
        return None
    url = (
        permalink
        if permalink.startswith("http")
        else f"https://www.reddit.com{permalink}"
    )
    body = str(data.get("selftext") or "").strip()
    author = str(data.get("author") or "").strip() or None
    created = data.get("created_utc")
    posted_at = None
    if isinstance(created, (int, float)):
        posted_at = datetime.fromtimestamp(created, tz=UTC).isoformat()
    return {
        "source_id": f"{subreddit}:{post_id}",
        "title": title,
        "description": body or title,
        "url": url,
        "company": f"r/{subreddit}" + (f" · u/{author}" if author else ""),
        "posted_at": posted_at,
        "budget_min": None,
        "budget_max": None,
        "metadata": {
            "location": "Remote",
            "tags": ["reddit", "hiring", subreddit.lower()],
            "subreddit": subreddit,
            "author": author,
        },
    }


async def search_hiring(
    *, limit: int = 20, query: str | None = None
) -> list[dict[str, Any]]:
    """Fetch recent [Hiring] posts from configured subreddits via OAuth."""
    if not reddit_configured():
        raise SourceNotConfiguredError(
            "Reddit is not configured. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET."
        )

    settings = get_settings()
    subreddits = _parse_subreddits(settings.reddit_subreddits)
    keyword = (query or "").strip().lower()
    per_sub = max(5, min(100, limit * 2))
    rows: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        token = await _access_token(client)
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": settings.reddit_user_agent,
        }
        for subreddit in subreddits:
            response = await client.get(
                f"{OAUTH_BASE}/r/{subreddit}/new",
                params={"limit": per_sub, "raw_json": 1},
                headers=headers,
            )
            if response.status_code >= 400:
                logger.warning(
                    "Reddit r/%s fetch failed: %s %s",
                    subreddit,
                    response.status_code,
                    response.text[:200],
                )
                continue
            listing = response.json().get("data", {}).get("children") or []
            for child in listing:
                row = _row_from_post(child, subreddit=subreddit)
                if row is None:
                    continue
                if keyword:
                    blob = f"{row['title']} {row['description']}".lower()
                    if keyword not in blob:
                        continue
                rows.append(row)
                if len(rows) >= limit:
                    return rows[:limit]
    return rows[:limit]
