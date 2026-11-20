"""SSRF-safe server-side fetch for public allowlisted destinations."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

# Public business / ATS / career hosts we may fetch for employer research.
DEFAULT_ALLOWLIST_SUFFIXES = (
    "greenhouse.io",
    "boards.greenhouse.io",
    "lever.co",
    "jobs.lever.co",
    "ashbyhq.com",
    "jobs.ashbyhq.com",
    "remoteok.com",
    "arbeitnow.com",
    "himalayas.app",
    "jobicy.com",
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "wellfound.com",
    "angel.co",
    "crunchbase.com",
    "wikipedia.org",
    "github.com",
    "gitlab.com",
)

MAX_BYTES = 512_000
MAX_REDIRECTS = 3
TIMEOUT = 8.0


@dataclass(slots=True)
class SafeFetchResult:
    ok: bool
    url: str
    final_url: str | None = None
    status_code: int | None = None
    content_type: str | None = None
    text: str | None = None
    error: str | None = None
    blocked_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "url": self.url,
            "final_url": self.final_url,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "text_excerpt": (self.text or "")[:2000] if self.text else None,
            "error": self.error,
            "blocked_reason": self.blocked_reason,
        }


def _is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def host_allowed(host: str, allow_suffixes: tuple[str, ...] = DEFAULT_ALLOWLIST_SUFFIXES) -> bool:
    h = host.lower().strip().rstrip(".")
    if not h or h in {"localhost", "metadata.google.internal"}:
        return False
    if h.endswith(".local") or h.endswith(".internal"):
        return False
    for suffix in allow_suffixes:
        s = suffix.lower()
        if h == s or h.endswith("." + s):
            return True
    return False


def validate_public_url(
    url: str,
    *,
    allow_suffixes: tuple[str, ...] = DEFAULT_ALLOWLIST_SUFFIXES,
    resolve_dns: bool = True,
) -> tuple[bool, str | None]:
    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001
        return False, "invalid_url"
    if parsed.scheme not in {"http", "https"}:
        return False, "scheme_not_allowed"
    host = parsed.hostname
    if not host:
        return False, "missing_host"
    if not host_allowed(host, allow_suffixes):
        return False, "host_not_allowlisted"
    # Literal IP in URL
    try:
        ipaddress.ip_address(host)
        if not _is_public_ip(host):
            return False, "private_ip"
    except ValueError:
        pass
    if resolve_dns:
        try:
            infos = socket.getaddrinfo(host, None)
            for info in infos:
                ip = info[4][0]
                if not _is_public_ip(ip):
                    return False, "resolved_private_ip"
        except socket.gaierror:
            return False, "dns_failed"
    return True, None


def sanitize_fetched_text(raw: str | None) -> str:
    if not raw:
        return ""
    text = raw
    # Strip scripts/styles and tags lightly
    text = re_sub_scripts(text)
    text = " ".join(text.split())
    return text[:8000]


def re_sub_scripts(text: str) -> str:
    import re

    clean = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    clean = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", clean)
    clean = re.sub(r"(?is)<iframe[^>]*>.*?</iframe>", " ", clean)
    clean = re.sub(r"(?s)<[^>]+>", " ", clean)
    # Neutralize embedded instruction cues in fetched pages too
    clean = re.sub(
        r"(?is)(?:ignore|disregard)\s+(?:all\s+)?(?:previous|prior)\s+instructions?",
        " ",
        clean,
    )
    return clean


async def safe_fetch_text(
    url: str,
    *,
    allow_suffixes: tuple[str, ...] = DEFAULT_ALLOWLIST_SUFFIXES,
    max_bytes: int = MAX_BYTES,
) -> SafeFetchResult:
    ok, reason = validate_public_url(url, allow_suffixes=allow_suffixes)
    if not ok:
        return SafeFetchResult(ok=False, url=url, blocked_reason=reason)

    current = url
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=False,
            headers={"User-Agent": "SignalDeskTrustResearch/0.1 (+ssrf-safe)"},
        ) as client:
            for _ in range(MAX_REDIRECTS + 1):
                ok, reason = validate_public_url(current, allow_suffixes=allow_suffixes)
                if not ok:
                    return SafeFetchResult(
                        ok=False, url=url, final_url=current, blocked_reason=reason
                    )
                resp = await client.get(current)
                if resp.status_code in {301, 302, 303, 307, 308}:
                    loc = resp.headers.get("location")
                    if not loc:
                        return SafeFetchResult(
                            ok=False,
                            url=url,
                            final_url=current,
                            status_code=resp.status_code,
                            blocked_reason="redirect_missing_location",
                        )
                    current = urljoin(current, loc)
                    continue
                ctype = resp.headers.get("content-type", "")
                if "html" not in ctype and "text" not in ctype and "json" not in ctype:
                    return SafeFetchResult(
                        ok=False,
                        url=url,
                        final_url=str(resp.url),
                        status_code=resp.status_code,
                        content_type=ctype,
                        blocked_reason="content_type_not_text",
                    )
                body = resp.content[:max_bytes]
                text = sanitize_fetched_text(body.decode("utf-8", errors="replace"))
                return SafeFetchResult(
                    ok=resp.is_success,
                    url=url,
                    final_url=str(resp.url),
                    status_code=resp.status_code,
                    content_type=ctype,
                    text=text,
                    error=None if resp.is_success else f"http_{resp.status_code}",
                )
        return SafeFetchResult(
            ok=False, url=url, final_url=current, blocked_reason="too_many_redirects"
        )
    except Exception as exc:  # noqa: BLE001
        return SafeFetchResult(ok=False, url=url, error=str(exc)[:200])
