from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from config.settings import get_settings
from app.core.logging.logger import get_logger

logger = get_logger(__name__)

TOKEN_URL = "https://www.upwork.com/api/v3/oauth2/token"
AUTHORIZE_URL = "https://www.upwork.com/ab/account-security/oauth2/authorize"
GRAPHQL_URL = "https://api.upwork.com/graphql"
TOKEN_FILE = Path(__file__).resolve().parents[2] / "data" / "upwork_tokens.json"

JOB_SEARCH_QUERY = """
query SearchJobs($searchExpression: String, $paging: MarketplaceJobPostingsSearchPagingInput) {
  marketplaceJobPostingsSearch(marketPlaceJobFilter: {searchExpression_eq: $searchExpression}, paging: $paging) {
    totalCount
    edges {
      node {
        id
        title
        description
        createdDateTime
        job {
          id
          content {
            title
            description
          }
        }
        skills {
          name
        }
        amount {
          rawValue
          currency
        }
        client {
          location {
            country
          }
        }
        ciphertext
        freelancersToHire
      }
    }
  }
}
"""

# Fallback query shape used by older/public docs examples
JOB_SEARCH_QUERY_LEGACY = """
query SearchJobs($searchExpression: String, $paging: PagingInput) {
  marketplaceJobPostingsSearch(searchExpression: $searchExpression, paging: $paging) {
    total
    results {
      id
      title
      description
      skills { name }
      budget { amount currency }
      createdDateTime
      client { id country }
      ciphertext
      url
    }
  }
}
"""


class SourceNotConfiguredError(RuntimeError):
    """Raised when marketplace credentials are missing."""


@dataclass
class UpworkTokens:
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int | None = None


def upwork_configured() -> bool:
    settings = get_settings()
    tokens = load_tokens()
    return bool(settings.upwork_access_token or (tokens and tokens.access_token))


def load_tokens() -> UpworkTokens | None:
    settings = get_settings()
    if settings.upwork_access_token:
        return UpworkTokens(
            access_token=settings.upwork_access_token,
            refresh_token=settings.upwork_refresh_token,
        )
    if not TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        access = data.get("access_token")
        if not access:
            return None
        return UpworkTokens(
            access_token=access,
            refresh_token=data.get("refresh_token"),
            token_type=data.get("token_type") or "Bearer",
            expires_in=data.get("expires_in"),
        )
    except Exception:
        logger.exception("Failed to load Upwork tokens")
        return None


def save_tokens(tokens: UpworkTokens) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(
        json.dumps(
            {
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "token_type": tokens.token_type,
                "expires_in": tokens.expires_in,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def build_authorize_url(state: str = "signal-desk") -> str:
    settings = get_settings()
    if not settings.upwork_client_id:
        raise SourceNotConfiguredError("UPWORK_CLIENT_ID is not set")
    redirect = settings.upwork_redirect_uri
    return (
        f"{AUTHORIZE_URL}"
        f"?response_type=code"
        f"&client_id={settings.upwork_client_id}"
        f"&redirect_uri={redirect}"
        f"&state={state}"
    )


async def exchange_code_for_tokens(code: str) -> UpworkTokens:
    settings = get_settings()
    if not settings.upwork_client_id or not settings.upwork_client_secret:
        raise SourceNotConfiguredError("UPWORK_CLIENT_ID / UPWORK_CLIENT_SECRET required")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.upwork_redirect_uri,
                "client_id": settings.upwork_client_id,
                "client_secret": settings.upwork_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        payload = response.json()

    tokens = UpworkTokens(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token"),
        token_type=payload.get("token_type") or "Bearer",
        expires_in=payload.get("expires_in"),
    )
    save_tokens(tokens)
    return tokens


async def refresh_access_token(refresh_token: str) -> UpworkTokens:
    settings = get_settings()
    if not settings.upwork_client_id or not settings.upwork_client_secret:
        raise SourceNotConfiguredError("UPWORK_CLIENT_ID / UPWORK_CLIENT_SECRET required to refresh")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.upwork_client_id,
                "client_secret": settings.upwork_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        payload = response.json()

    tokens = UpworkTokens(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token") or refresh_token,
        token_type=payload.get("token_type") or "Bearer",
        expires_in=payload.get("expires_in"),
    )
    save_tokens(tokens)
    return tokens


async def _graphql(access_token: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            GRAPHQL_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"query": query, "variables": variables},
        )
        if response.status_code == 401:
            raise PermissionError("upwork_unauthorized")
        response.raise_for_status()
        payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(f"Upwork GraphQL errors: {payload['errors']}")
    return payload.get("data") or {}


def _normalize_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    search = data.get("marketplaceJobPostingsSearch") or {}
    rows: list[dict[str, Any]] = []

    # Legacy flat results shape
    for item in search.get("results") or []:
        rows.append(item)

    # Connection/edges shape
    for edge in search.get("edges") or []:
        node = edge.get("node") if isinstance(edge, dict) else None
        if node:
            rows.append(node)

    return rows


def _row_to_fields(row: dict[str, Any]) -> dict[str, Any]:
    job_content = ((row.get("job") or {}).get("content")) or {}
    title = row.get("title") or job_content.get("title") or "Untitled"
    description = row.get("description") or job_content.get("description") or title
    skills = [str(skill.get("name")).lower() for skill in (row.get("skills") or []) if isinstance(skill, dict) and skill.get("name")]

    budget = row.get("budget") or {}
    amount = row.get("amount") or {}
    budget_value = budget.get("amount")
    if budget_value is None:
        budget_value = amount.get("rawValue")
    try:
        budget_num = float(budget_value) if budget_value is not None else None
    except (TypeError, ValueError):
        budget_num = None

    source_id = str(row.get("id") or row.get("ciphertext") or title)
    ciphertext = row.get("ciphertext")
    url = row.get("url")
    if not url and ciphertext:
        url = f"https://www.upwork.com/jobs/{ciphertext}"
    if not url:
        url = f"https://www.upwork.com/nx/search/jobs/?q={source_id}"

    client = row.get("client") or {}
    location = None
    if isinstance(client.get("location"), dict):
        location = client["location"].get("country")
    elif client.get("country"):
        location = client.get("country")

    return {
        "source_id": source_id,
        "title": str(title),
        "description": str(description),
        "url": str(url),
        "company": "Upwork client",
        "budget_min": budget_num,
        "budget_max": budget_num,
        "posted_at": row.get("createdDateTime"),
        "tags": skills,
        "location": location or "Remote",
    }


async def search_jobs(*, query: str = "python", limit: int = 20) -> list[dict[str, Any]]:
    tokens = load_tokens()
    if not tokens:
        raise SourceNotConfiguredError(
            "Upwork is not connected. Set UPWORK_ACCESS_TOKEN or complete OAuth via /integrations/upwork/authorize"
        )

    variables = {
        "searchExpression": query,
        "paging": {"offset": 0, "count": limit},
    }

    try:
        data = await _graphql(tokens.access_token, JOB_SEARCH_QUERY_LEGACY, variables)
    except PermissionError:
        if not tokens.refresh_token:
            raise SourceNotConfiguredError("Upwork access token expired and no refresh token available")
        tokens = await refresh_access_token(tokens.refresh_token)
        data = await _graphql(tokens.access_token, JOB_SEARCH_QUERY_LEGACY, variables)
    except RuntimeError:
        # Newer schema may expect marketPlaceJobFilter shape
        try:
            data = await _graphql(
                tokens.access_token,
                JOB_SEARCH_QUERY,
                {
                    "searchExpression": query,
                    "paging": {"offset": 0, "count": limit},
                },
            )
        except Exception:
            logger.exception("Upwork job search failed with both query shapes")
            raise

    return [_row_to_fields(row) for row in _normalize_rows(data)][:limit]
