"""Hacker News hiring hunt — official Firebase API, 'Ask HN' hiring threads."""

from __future__ import annotations

import asyncio
import html
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.logging.logger import get_logger
from backend.application.services.duplicate_detection import JobCandidate

logger = get_logger(__name__)

HN_BASE_URL = "https://hacker-news.firebaseio.com/v0"
WHO_IS_HIRING_USER_URL = f"{HN_BASE_URL}/user/whoishiring.json"
ITEM_URL_TEMPLATE = f"{HN_BASE_URL}/item/{{item_id}}.json"
COMMENT_WEB_URL_TEMPLATE = "https://news.ycombinator.com/item?id={comment_id}"

SEEKING_FREELANCER_RE = re.compile(r"seeking\s*freelancer", re.IGNORECASE)
SEEKING_WORK_RE = re.compile(r"seeking\s*work", re.IGNORECASE)
CONTRACT_SIGNALS_RE = re.compile(
    r"\b(freelance|contract|contractor|consultant|part-time|hourly|project-based|c2c)\b",
    re.IGNORECASE,
)
HTML_TAG_RE = re.compile(r"<[^>]+>")


def _clean_html(text: str) -> str:
    """Strip HTML tags and unescape entities into clean plain text."""
    if not text:
        return ""
    # Replace paragraph breaks with newlines
    normalized = re.sub(r"</?p\s*/?>", "\n\n", text, flags=re.IGNORECASE)
    normalized = re.sub(r"<br\s*/?>", "\n", normalized, flags=re.IGNORECASE)
    stripped = HTML_TAG_RE.sub("", normalized)
    unescaped = html.unescape(stripped)
    return "\n".join(line.strip() for line in unescaped.splitlines() if line.strip())


def _parse_hn_header(
    plain_text: str,
) -> tuple[str, str | None, list[str]]:
    """
    Parse standard HN comment header (e.g. 'Company | Role | Location | Contract').
    Returns (title, company, tags).
    """
    lines = [line.strip() for line in plain_text.splitlines() if line.strip()]
    first_line = lines[0] if lines else "Contract Role"

    parts = [part.strip() for part in first_line.split("|") if part.strip()]
    if len(parts) >= 2:
        company = parts[0]
        role = parts[1]
        title = f"{company} — {role}"
        tags = parts[2:]
        return title, company, tags
    return first_line[:120], None, []


async def _fetch_item(client: httpx.AsyncClient, item_id: int) -> dict[str, Any] | None:
    try:
        response = await client.get(ITEM_URL_TEMPLATE.format(item_id=item_id))
        if response.status_code == 200:
            return response.json()
    except Exception as exc:
        logger.debug("Failed to fetch HN item %d: %s", item_id, exc)
    return None


async def fetch_hn_hiring_jobs(
    *,
    limit: int = 30,
    query: str | None = None,
    timeout: float = 20.0,
) -> list[JobCandidate]:
    """
    Fetch high-signal freelance and contract leads from official HN hiring threads.
    Zero third-party API keys or costs required.
    """
    headers = {"User-Agent": "SignalDesk/1.0 (+https://signaldesk.com)"}
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        # 1. Fetch user 'whoishiring' submissions
        try:
            resp = await client.get(WHO_IS_HIRING_USER_URL)
            resp.raise_for_status()
            user_data = resp.json()
        except Exception as exc:
            logger.warning("Could not fetch HN whoishiring user profile: %s", exc)
            return []

        submitted_ids: list[int] = user_data.get("submitted", [])[:15]
        if not submitted_ids:
            return []

        # 2. Inspect stories for the latest 'Seeking freelancer' or 'Who is hiring' threads
        story_tasks = [_fetch_item(client, sid) for sid in submitted_ids]
        stories = await asyncio.gather(*story_tasks)

        target_threads: list[dict[str, Any]] = []
        seen_threads: set[int] = set()
        for story in stories:
            if not story or not isinstance(story, dict):
                continue
            sid = story.get("id")
            if sid in seen_threads:
                continue
            seen_threads.add(sid)

            title = story.get("title", "")
            if "seeking freelancer" in title.lower() or "who is hiring" in title.lower():
                target_threads.append(story)
            if len(target_threads) >= 2:
                break

        if not target_threads:
            return []

        # 3. Collect top comment kids from the threads (deduped)
        comment_ids: list[tuple[int, str]] = []
        seen_cids: set[int] = set()
        for thread in target_threads:
            thread_title = thread.get("title", "")
            kids = thread.get("kids", [])
            is_freelance_thread = "seeking freelancer" in thread_title.lower()
            mode = "freelancer" if is_freelance_thread else "hiring"
            for kid in kids[:80]:
                if kid not in seen_cids:
                    seen_cids.add(kid)
                    comment_ids.append((kid, mode))

        # 4. Fetch comments concurrently with semaphore
        semaphore = asyncio.Semaphore(15)

        async def fetch_comment_safe(cid: int, mode: str) -> tuple[dict[str, Any] | None, str]:
            async with semaphore:
                data = await _fetch_item(client, cid)
                return data, mode

        comment_tasks = [fetch_comment_safe(cid, mode) for cid, mode in comment_ids]
        results = await asyncio.gather(*comment_tasks)

        # 5. Filter & construct JobCandidates
        query_terms = [q.lower().strip() for q in (query or "").split() if q.strip()]
        candidates: list[JobCandidate] = []

        for item, mode in results:
            if not item or not isinstance(item, dict):
                continue
            if item.get("deleted") or item.get("dead"):
                continue

            raw_text = item.get("text", "")
            if not raw_text:
                continue

            plain_text = _clean_html(raw_text)

            # Filtering rules:
            if mode == "freelancer":
                # In freelancer thread: must be SEEKING FREELANCER, skip SEEKING WORK
                if SEEKING_WORK_RE.search(plain_text):
                    continue
                if not SEEKING_FREELANCER_RE.search(plain_text) and not CONTRACT_SIGNALS_RE.search(plain_text):
                    continue
            else:
                # In regular "Who is hiring" thread: must explicitly offer contract/freelance work
                if not CONTRACT_SIGNALS_RE.search(plain_text):
                    continue

            # Check search query terms if provided
            if query_terms:
                haystack = plain_text.lower()
                if not any(term in haystack for term in query_terms):
                    continue

            comment_id = str(item.get("id"))
            author = item.get("by") or "Hacker News Client"
            created_epoch = item.get("time")
            posted_at = (
                datetime.fromtimestamp(created_epoch, tz=UTC).isoformat()
                if created_epoch
                else datetime.now(UTC).isoformat()
            )

            title, company, tags = _parse_hn_header(plain_text)
            if not company:
                company = author

            url = COMMENT_WEB_URL_TEMPLATE.format(comment_id=comment_id)

            candidates.append(
                JobCandidate(
                    source_name="hn_hiring",
                    source_id=comment_id,
                    title=title,
                    description=plain_text,
                    url=url,
                    company=company,
                    budget_min=None,
                    budget_max=None,
                    posted_at=posted_at,
                    metadata={
                        "author": author,
                        "hn_thread": mode,
                        "tags": tags + ["hacker-news", "freelance"],
                        "contract_verified": True,
                    },
                )
            )

            if len(candidates) >= limit:
                break

        return candidates
