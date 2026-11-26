"""Page-type classifier for opportunity URLs (rules + optional LLM).

Keeps only single, specific contract/freelance postings. Rejects job boards,
aggregators, careers hubs, listing/search pages, portfolios, and free-host spam.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

PAGE_TYPE_JOB_POST = "job_post"
PAGE_TYPE_LISTICLE = "listicle"
PAGE_TYPE_BOARD_INDEX = "board_index"
PAGE_TYPE_CAREERS_HUB = "careers_hub"
PAGE_TYPE_PORTFOLIO = "portfolio"
PAGE_TYPE_FULL_TIME = "full_time_employee"
PAGE_TYPE_NON_DEV = "non_dev"
PAGE_TYPE_SPAM_HOST = "spam_host"
PAGE_TYPE_UNKNOWN = "unknown"

# Hosts that never carry a single contract posting (listicles / directories / SEO hubs).
ALWAYS_NOISE_HOSTS: tuple[str, ...] = (
    "starterindex.com",
    "beaconbid.com",
    "andrejgajdos.com",
    "robinwieruch.de",
    "codesquad.org",
    "zippia.com",
    "instahyre.com",
    "crossover.com",
    "levels.fyi",
    "jobboardsearch.com",
    "theantijobboard.com",
    "anti-job-board.com",
    "techteems.com",
    "feedinkoo.com",
    # Non-posting / agency-homepages / FTE board hosts mistaken for contract roles.
    "dmepdac.com",
    "builtin.com",
    "aplin.com",
    "edtech.com",
    "helloworld.rs",
    "myjobmag.co.za",
    "myjobmag.com",

    # News / local-media hosts (not contract postings).
    "alohastatedaily.com",
    "staradvertiser.com",
    "hawaiinewsnow.com",
    "kitv.com",
    "civilbeat.org",
    "techcrunch.com",
    "theverge.com",
    "wired.com",
    "arstechnica.com",
    "bloomberg.com",
    "reuters.com",
    "cnn.com",
    "bbc.com",
    "nytimes.com",
)

# Aggregators / boards: reject index/search pages, but keep single-job URLs.
BOARD_AGGREGATOR_HOSTS: tuple[str, ...] = (
    "remoteleaf.com",
    "jobleads.com",
    "jobleads.co",
    "jobright.ai",
    "dailyremote.com",
    "remoterocketship.com",
    "turing.com",
    "toptal.com",
    "arc.dev",
    "kickstartremote.com",
    "app.joinhandshake.com",
    "joinhandshake.com",
    "workingnomads.com",
    "workingnomads.co",
    "opentalent.in",
    "justjoin.it",
    "wearedevelopers.com",
    "4dayweek.io",
    "dynamitejobs.com",
    "hiddenjobs.dev",
    "hiredoor.in",
    "reactjobs.io",
    "freelance-informatique.fr",
    "weekday.works",
    "cwjobs.co.uk",
    "reed.co.uk",
    "totaljobs.com",
    "indeed.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "dice.com",
    "simplyhired.com",
    "linkedin.com",
    "wellfound.com",
    "angel.co",
    "ycombinator.com",
    "remoteok.com",
    "weworkremotely.com",
    "flexjobs.com",
    "remoteco.com",
    "nodesk.co",
    "himalayas.app",
    "otta.com",
    "codingjobboard.com",
    "nofluffjobs.com",
    "landing.jobs",
    "usajobs.gov",
    "contractoruk.com",
    "calopps.org",
    "marylandbids.com",
    "gov.uk",
    "indeed.co.uk",
    "europol.europa.eu",
    "mwaa.com",
    "free-work.com",
    "remotejobs.org",
    "opentrain.ai",
    "xpertise-recruitment.com",
)

FREE_HOST_SUFFIXES: tuple[str, ...] = (
    ".wuaze.com",
    ".infinityfreeapp.com",
    ".rf.gd",
    ".epizy.com",
    ".000webhostapp.com",
    ".netlify.app",
    ".vercel.app",
    ".pages.dev",
    ".github.io",
    ".web.app",
    ".firebaseapp.com",
    ".blogspot.com",
    ".wordpress.com",
    ".wixsite.com",
    ".square.site",
    ".weebly.com",
    ".carrd.co",
    ".up.railway.app",
    ".railway.app",
    ".onrender.com",
    ".fly.dev",
    ".herokuapp.com",
    ".glitch.me",
    ".repl.co",
    ".ngrok.io",
    ".ngrok-free.app",
)

LISTING_PAGE_TEXT_RE = re.compile(
    r"(?:"
    r"\bjobs?\s+in\b"
    r"|\b\d+[,\d]*\+?\s+(?:it\s*&?\s*technology\s+)?(?:contract\s+)?jobs?\b"
    r"|\bsearch\s+(?:our\s+)?(?:job|jobs)\b"
    r"|\bcareers?\s*(?:&|and)\s*(?:recruitment|benefits)\b"
    r"|\btechnology\s+careers?\b"
    r"|\bbrowse\s+(?:all\s+)?(?:open\s+)?(?:roles|positions|jobs)\b"
    r"|\bview\s+all\s+(?:jobs|openings|roles)\b"
    r"|\bopen\s+(?:positions?|vacancies)\b"
    r"|\bcurrent\s+(?:openings?|contracting\s+opportunities)\b"
    r"|\bjob\s+(?:board|listings?|search|alerts?)\b"
    r"|\bfind\s+(?:your\s+next\s+)?(?:remote\s+)?(?:job|role|gig)\b"
    r"|\bexplore\s+(?:remote\s+)?(?:jobs|careers|roles)\b"
    r"|\bbids?,?\s*rfps?\b"
    r"|\bcontracting\s+opportunities\b"
    r")",
    re.IGNORECASE,
)

FULL_TIME_ONLY_RE = re.compile(
    r"(?:"
    r"\bfull[\s-]?time\b"
    r"|\bpermanent\b"
    r"|\bsalaried\b"
    r"|\bw-?2\b"
    r"|\bbenefits\s+package\b"
    r"|\b401\s*\(?k\)?\b"
    r"|\bpto\b"
    r"|\bpaid\s+time\s+off\b"
    r"|\bstaff\s+(?:software\s+)?(?:engineer|developer)\b"
    r"|\bpermanent\s+(?:employee|employment|role|position|hire)\b"
    r")"
    r"(?!.*\b(?:contract|freelance|fractional|hourly|contractor|consultant|gig)\b)",
    re.IGNORECASE | re.DOTALL,
)

CONTRACT_SIGNAL_RE = re.compile(
    r"\b(?:contract|freelance|fractional|hourly|contractor|consultant|gig|"
    r"1099|fixed[\s-]?price|project[\s-]?based)\b",
    re.IGNORECASE,
)

NON_DEV_ROLE_RE = re.compile(
    r"(?:"
    r"\b(?:customer|client|technical)?\s*support\s+(?:specialist|agent|engineer|representative|associate)\b"
    r"|\b(?:trainer|training\s+specialist|instructor|teacher|coach)\b"
    r"|\b(?:recruiter|talent\s+acquisition|hr\s+manager|people\s+ops)\b"
    r"|\b(?:sales\s+(?:executive|manager|representative)|account\s+executive)\b"
    r"|\b(?:receptionist|office\s+manager|administrative\s+assistant)\b"
    r")",
    re.IGNORECASE,
)

# Recruiter landings / domain indexes / generic board titles — not a single posting.
THIN_LISTING_TITLE_RE = re.compile(
    r"(?:"
    r"^job\s*:\s*"
    r"|\bai\s+training\s+jobs?\b"
    r"|\bremote\s+[a-z][a-z\s]{0,40}?\s+ai\s+training\s+jobs?\b"
    r"|\b(?:browse|search|view)\s+(?:all\s+)?(?:jobs?|openings|careers)\b"
    r"|\bmyworkdayjobs\.com\b"
    r")",
    re.IGNORECASE,
)

DOMAIN_INDEX_PATH_RE = re.compile(
    r"(?:"
    r"/jobs?/domain/"
    r"|/jobs?/category/"
    r"|/jobs?/categories/"
    r"|/jobs?/skills?/"
    r"|/remote-jobs?/?$"
    r"|/careers?/search"
    r")",
    re.IGNORECASE,
)

SINGLE_POSTING_PATH_RE = re.compile(
    r"(?:"
    # /jobs/<slug>, /remote-job/<slug>, /opening/<id> — not bare /jobs or /remote-jobs hubs
    r"/(?:jobs?|openings?|positions?|j|role|posting|remote-jobs?)/[a-z0-9][a-z0-9_-]{3,}"
    r"|/job/\d+"
    r"|/[a-z0-9-]{6,}-\d{3,}"  # slug-123 style single posts
    r")",
    re.IGNORECASE,
)

LISTICLE_RE = re.compile(
    r"(?:"
    r"\btop\s+\d+\b"
    r"|\b\d+\s+(?:best|free|open[\s-]?source|amazing|essential)\b"
    r"|\b\d+[,\d]*\s+[\w,+/\s&.-]{0,80}\b(?:boilerplates?|starter\s+kits?|templates?|resources?|tools?|libraries|frameworks)\b"
    r"|\bbest\s+(?:freelance|remote)\b"
    r"|\bhow\s+to\s+(?:become|hire|find|get|start|land|choose)\b"
    r"|\bbecome\s+a\s+(?:developer|engineer|freelancer|programmer)\b"
    r"|\b(?:ultimate|complete|definitive)\s+guide\b"
    r"|\bboilerplates?\b"
    r"|\bstarter\s+kits?\b"
    r"|\bawesome-[\w-]+\b"
    r"|\banti[\s-]?job[\s-]?board\b"
    r"|\bjob\s+board\b"
    r"|\b(?:sitemap|round[\s-]?up|curated\s+list|directory\s+of)\b"
    r"|\bjobs?\s+near\s+me\b"
    r"|\b\d+\s+remote\s+\w+\s+job\s+openings?\b"
    r"|\bapply\s+to\s+\d+\s+remote\b"
    r")",
    re.IGNORECASE,
)

# Real postings mention a role/engagement; listicles/directories usually do not.
HIRING_SIGNAL_RE = re.compile(
    r"(?:"
    r"\b(?:hir(?:e|ing)|looking\s+for|seeking|we're\s+hiring|now\s+hiring)\b"
    r"|\b(?:freelance|contractor|contract(?:ing)?|consultant|gig)\b"
    r"|\b(?:role|position|opening|vacancy|apply|application)\b"
    r"|\b(?:engineer|developer|designer|architect|specialist)\b"
    r"|\b(?:full[\s-]?stack|back[\s-]?end|front[\s-]?end|devops|sre)\b"
    r")",
    re.IGNORECASE,
)

MONTHLY_SALARY_RE = re.compile(
    r"(?:"
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(k)?\s*(?:/|per)\s*(?:mo(?:nth)?|m)\b"
    r"|\b([\d,]+(?:\.\d+)?)\s*(k)?\s*(?:usd|dollars?)\s*(?:/|per)\s*(?:mo(?:nth)?|m)\b"
    r"|\$\s*([\d,]+(?:\.\d+)?)\s*(k)?\s*(?:[\u2013\-]\$?\s*[\d,]+(?:\.\d+)?\s*(k)?)?\s*"
    r"(?:/|per)?\s*(?:yr|year|annual(?:ly)?)\b"
    r"|\$\s*([\d,]{5,}(?:\.\d+)?)\b"
    r"|\b([\d,]+(?:\.\d+)?)\s*(k)\b"
    r")",
    re.IGNORECASE,
)

PORTFOLIO_RE = re.compile(
    r"\b(?:hire\s+me|work\s+with\s+me|my\s+portfolio|available\s+for\s+hire|developer\s+for\s+hire)\b",
    re.IGNORECASE,
)

TENDER_RE = re.compile(
    r"(?:"
    r"\be-?tenders?\b"
    r"|\btender\s+(?:notice|no\.?|number|id|document|invited|invitation|submission|portal|reference|for)\b"
    r"|\binvitation\s+(?:to|for)\s+(?:tender|bids?|rfp|rfq|eoi)\b"
    r"|\brequest\s+for\s+(?:proposals?|quotations?|tenders?|bids?|information|qualifications?)\b"
    r"|\b(?:rfp|rfq|rft|ifb|eoi)\s*(?:#|no\.?|number|notice|submission|document|reference|\b)"
    r"|\b(?:public|government|municipal|ministry)\s+(?:procurement|tender)\b"
    r"|\b(?:earnest\s+money|bid\s+security|bid\s+bond|sealed\s+bids?|corrigendum|procurement\s+notice)\b"
    r")",
    re.IGNORECASE,
)

TENDER_HOST_MARKERS: tuple[str, ...] = (
    "tendersontime.com",
    "tendertiger.com",
    "biddetail.com",
    "globaltenders.com",
    "dgmarket.com",
    "ted.europa.eu",
    "find-tender.service.gov.uk",
    "etenders.gov.in",
    "gem.gov.in",
)

BLOG_PATH_MARKERS: tuple[str, ...] = (
    "/blog/",
    "/blogs/",
    "/article/",
    "/articles/",
    "/guide/",
    "/guides/",
    "/tutorial/",
    "/tutorials/",
    "/insights/",
    "/resources/",
)


def _host_path(url: str | None) -> tuple[str, str]:
    raw = (url or "").strip().lower()
    if not raw:
        return "", ""
    try:
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        host = (parsed.hostname or "").lower().removeprefix("www.")
        path = (parsed.path or "").lower()
        return host, path
    except Exception:
        return raw, raw


_NOISE_PAGE_TYPES = frozenset(
    {
        PAGE_TYPE_LISTICLE,
        PAGE_TYPE_BOARD_INDEX,
        PAGE_TYPE_CAREERS_HUB,
        PAGE_TYPE_PORTFOLIO,
        PAGE_TYPE_FULL_TIME,
        PAGE_TYPE_NON_DEV,
        PAGE_TYPE_SPAM_HOST,
    }
)


def classify_page_type(
    title: str | None,
    description: str | None = None,
    url: str | None = None,
    company: str | None = None,
    *,
    enrichment: dict[str, Any] | None = None,
) -> str:
    """Rule-based page type.

    Rules always win for rejection so a stale enrichment.page_type=job_post
    cannot keep listicles/boards (e.g. starterindex) in the lead list.
    Enrichment may only make classification *more* restrictive.
    """
    host, path = _host_path(url)
    blob = f"{title or ''} {description or ''} {company or ''}"
    url_lower = (url or "").lower()

    if host and any(host == s.lstrip(".") or host.endswith(s) for s in FREE_HOST_SUFFIXES):
        return PAGE_TYPE_SPAM_HOST

    if any(host == h or host.endswith(f".{h}") for h in TENDER_HOST_MARKERS):
        return PAGE_TYPE_LISTICLE
    if any(marker in url_lower for marker in BLOG_PATH_MARKERS):
        return PAGE_TYPE_LISTICLE
    if TENDER_RE.search(blob):
        return PAGE_TYPE_LISTICLE

    # Listicle/directory hosts never yield a single contract opportunity.
    if any(host == h or host.endswith(f".{h}") for h in ALWAYS_NOISE_HOSTS):
        return PAGE_TYPE_LISTICLE

    # Board aggregators: keep deep single-job URLs; drop index/search hubs.
    # Require a numeric or long opaque id so /jobs/python stays a hub.
    if any(host == h or host.endswith(f".{h}") for h in BOARD_AGGREGATOR_HOSTS):
        deep = bool(SINGLE_POSTING_PATH_RE.search(path)) and bool(
            re.search(r"(?:\d{3,}|[a-f0-9]{8,})", path, re.IGNORECASE)
        )
        if not deep:
            return PAGE_TYPE_BOARD_INDEX

    if (
        host.startswith("careers.")
        or host.startswith("career.")
        or host.startswith("jobs.")
        or host.endswith(".teamtailor.com")
        or host.endswith(".workable.com")
        or host == "apply.workable.com"
        or host.startswith("career.")
        or "career.luxoft.com" in host
        or "jobs.makesense.org" in host
        or "jobs.natwestgroup.com" in host
        or "jobs.appliedmaterials.com" in host
    ):
        if not SINGLE_POSTING_PATH_RE.search(path):
            return PAGE_TYPE_CAREERS_HUB
        if path.rstrip("/") in {"", "/careers", "/career", "/jobs", "/join-us", "/joinus", "/openings"}:
            return PAGE_TYPE_CAREERS_HUB

    if DOMAIN_INDEX_PATH_RE.search(path):
        return PAGE_TYPE_BOARD_INDEX
    if THIN_LISTING_TITLE_RE.search(title or ""):
        return PAGE_TYPE_BOARD_INDEX
    # Bare recruiter/agency landings with no deep posting path.
    if re.search(r"^job\s*:\s*", title or "", re.IGNORECASE) or (
        re.fullmatch(r"job\s*:?\s*[\w.&'\s-]{2,60}", (title or "").strip(), re.IGNORECASE)
        and not SINGLE_POSTING_PATH_RE.search(path)
    ):
        return PAGE_TYPE_BOARD_INDEX
    if host.endswith(".myworkdayjobs.com") and not re.search(
        r"/job/", path, re.IGNORECASE
    ):
        return PAGE_TYPE_CAREERS_HUB
    if PORTFOLIO_RE.search(blob):
        return PAGE_TYPE_PORTFOLIO
    if LISTICLE_RE.search(blob) or LISTING_PAGE_TEXT_RE.search(blob):
        if LISTICLE_RE.search(blob):
            return PAGE_TYPE_LISTICLE
        return PAGE_TYPE_BOARD_INDEX
    if NON_DEV_ROLE_RE.search(title or ""):
        return PAGE_TYPE_NON_DEV
    has_contract = bool(CONTRACT_SIGNAL_RE.search(blob))
    enrichment_emp = ""
    if enrichment:
        enrichment_emp = " ".join(
            str(enrichment.get(k) or "")
            for k in (
                "employment_type",
                "engagement_type",
                "job_type",
                "workplace_type",
            )
        )
    fte_blob = f"{blob} {enrichment_emp}"
    if FULL_TIME_ONLY_RE.search(fte_blob) and not has_contract:
        # Permanent/FTE without contract language: keep only when monthly ≥ $10k.
        # No listed salary → reject (cannot prove it clears the bar).
        if not _monthly_salary_above(blob, enrichment, floor_usd=10_000):
            return PAGE_TYPE_FULL_TIME

    # Generic careers-hub path roots / titles on unknown hosts.
    if path.rstrip("/") in {
        "/careers",
        "/career",
        "/jobs",
        "/join-us",
        "/openings",
        "/vacancies",
        "/search",
        "/search-jobs",
    }:
        return PAGE_TYPE_CAREERS_HUB
    title_l = (title or "").lower()
    if re.search(
        r"\b(?:careers?(?:\s+and\s+benefits)?|open vacancies|current vacancies|"
        r"search jobs|technology careers|permanent employees)\b",
        title_l,
    ) and not SINGLE_POSTING_PATH_RE.search(path):
        return PAGE_TYPE_CAREERS_HUB

    if any(
        marker in url_lower
        for marker in ("/blog/", "/blogs/", "/article/", "/guide/", "/tutorial/")
    ):
        return PAGE_TYPE_LISTICLE

    # Content / roundup pages with no hiring language are not job posts.
    if not HIRING_SIGNAL_RE.search(blob) and not SINGLE_POSTING_PATH_RE.search(path):
        if re.search(
            r"\b(?:boilerplate|starter\s+kit|template|resource|tool|guide|sitemap|"
            r"directory|jobs?\s+near\s+me|job\s+openings?)\b",
            blob,
            re.IGNORECASE,
        ):
            return PAGE_TYPE_LISTICLE
        # News / spill / weather / politics stories with zero hiring language.
        if re.search(
            r"\b(?:fuel\s+spill|oil\s+spill|breaking\s+news|weather\s+alert|"
            r"police\s+say|died\s+at|killed\s+in|lawsuit\s+filed|election|"
            r"press\s+release)\b",
            blob,
            re.IGNORECASE,
        ):
            return PAGE_TYPE_LISTICLE

    # Require a hiring signal for unknown hosts — freelance discovery often
    # returns news pages that only match a skill keyword like "remote".
    if (
        not HIRING_SIGNAL_RE.search(blob)
        and not SINGLE_POSTING_PATH_RE.search(path)
        and host
        and host not in BOARD_AGGREGATOR_HOSTS
        and not any(host == h or host.endswith(f".{h}") for h in ALWAYS_NOISE_HOSTS)
    ):
        if not re.search(
            r"\b(?:engineer|developer|designer|freelance|contractor|hiring|"
            r"looking\s+for|apply\s+now|job\s+description|role)\b",
            blob,
            re.IGNORECASE,
        ):
            return PAGE_TYPE_LISTICLE

    rule_type = PAGE_TYPE_JOB_POST
    if enrichment:
        prior = str(enrichment.get("page_type") or "").strip().lower()
        if prior in _NOISE_PAGE_TYPES:
            return prior
    return rule_type


def has_hiring_signal(
    title: str | None,
    description: str | None = None,
    url: str | None = None,
) -> bool:
    """True when the listing mentions a role, engagement, or apply/hiring language."""
    _host, path = _host_path(url)
    blob = f"{title or ''} {description or ''}"
    if HIRING_SIGNAL_RE.search(blob):
        return True
    if SINGLE_POSTING_PATH_RE.search(path):
        return True
    return False


def estimate_monthly_salary_usd(
    text: str | None,
    enrichment: dict[str, Any] | None = None,
    *,
    budget_min: float | None = None,
    budget_max: float | None = None,
    period: str | None = None,
) -> float | None:
    """Best-effort monthly USD estimate from text / enrichment / budget fields."""
    if enrichment:
        period = period or str(enrichment.get("compensation_period") or enrichment.get("period") or "")
        for key in ("budget_max", "budget_min", "salary_max", "salary_min", "monthly_rate"):
            val = enrichment.get(key)
            if isinstance(val, (int, float)) and val > 0:
                p = (period or "").lower()
                if p in {"year", "yearly", "annual", "annually"}:
                    return float(val) / 12.0
                if p in {"hour", "hourly"}:
                    return float(val) * 160.0
                if p in {"day", "daily"}:
                    return float(val) * 20.0
                if p in {"week", "weekly"}:
                    return float(val) * 4.0
                return float(val)
    if budget_max or budget_min:
        amount = float(budget_max or budget_min or 0)
        p = (period or "").lower()
        if p in {"year", "yearly", "annual", "annually"}:
            return amount / 12.0
        if p in {"hour", "hourly"}:
            return amount * 160.0
        if amount >= 50_000:  # likely annual when period unknown
            return amount / 12.0
        return amount
    blob = text or ""
    # Strip benefit tokens that look like salaries (401k).
    scrubbed = re.sub(r"\b401\s*\(?k\)?\b", " ", blob, flags=re.IGNORECASE)
    for match in MONTHLY_SALARY_RE.finditer(scrubbed):
        full = match.group(0).lower()
        digits = re.search(r"([\d,]+(?:\.\d+)?)", full)
        if not digits:
            continue
        try:
            amount = float(digits.group(1).replace(",", ""))
        except ValueError:
            continue
        if re.search(r"\d\s*k\b", full) or "k/" in full or "k per" in full:
            amount *= 1000.0
        if "mo" in full:
            return amount
        # Bare "120k" → annual.
        if "k" in full or amount >= 50_000:
            return amount / 12.0
        return amount
    return None


def _monthly_salary_above(
    blob: str,
    enrichment: dict[str, Any] | None,
    *,
    floor_usd: float,
) -> bool:
    monthly = estimate_monthly_salary_usd(blob, enrichment)
    return monthly is not None and monthly >= floor_usd


def is_non_opportunity_noise(
    title: str | None,
    description: str | None = None,
    url: str | None = None,
    company: str | None = None,
    *,
    enrichment: dict[str, Any] | None = None,
    prefer_contract: bool = True,
    budget_min: float | None = None,
    budget_max: float | None = None,
    period: str | None = None,
) -> bool:
    page_type = classify_page_type(
        title, description, url, company, enrichment=enrichment
    )
    if page_type == PAGE_TYPE_JOB_POST:
        return False
    if page_type == PAGE_TYPE_FULL_TIME:
        if not prefer_contract:
            return False
        blob = f"{title or ''} {description or ''} {company or ''}"
        monthly = estimate_monthly_salary_usd(
            blob,
            enrichment,
            budget_min=budget_min,
            budget_max=budget_max,
            period=period,
        )
        if monthly is not None and monthly >= 10_000:
            return False
        return True
    return True


async def classify_page_type_llm(
    title: str | None,
    description: str | None = None,
    url: str | None = None,
) -> str | None:
    """Optional LLM refinement. Returns a page_type or None if unavailable/uncertain."""
    from backend.application.services.llm import LLMError, any_llm_configured, chat_completion

    if not any_llm_configured():
        return None
    excerpt = (description or "")[:1200]
    prompt = (
        "Classify this listing as exactly one of: "
        "job_post, listicle, board_index, careers_hub, portfolio, full_time_employee, non_dev, spam_host.\n"
        "job_post = a single specific freelance/contract role posting.\n"
        "board_index = job board, aggregator, or search/listing page.\n"
        "careers_hub = company careers index, not a single opening.\n"
        "Respond with JSON: {\"page_type\": \"...\", \"reason\": \"...\"}\n\n"
        f"Title: {title or ''}\nURL: {url or ''}\nDescription: {excerpt}"
    )
    try:
        result = await chat_completion(
            system="You classify web pages for a freelance opportunity desk. Be strict.",
            user=prompt,
            temperature=0.0,
            json_mode=True,
            timeout=20.0,
        )
        data = json.loads(result.content)
        page_type = str(data.get("page_type") or "").strip().lower()
        allowed = {
            PAGE_TYPE_JOB_POST,
            PAGE_TYPE_LISTICLE,
            PAGE_TYPE_BOARD_INDEX,
            PAGE_TYPE_CAREERS_HUB,
            PAGE_TYPE_PORTFOLIO,
            PAGE_TYPE_FULL_TIME,
            PAGE_TYPE_NON_DEV,
            PAGE_TYPE_SPAM_HOST,
        }
        return page_type if page_type in allowed else None
    except (LLMError, json.JSONDecodeError, TypeError, ValueError):
        return None


def domain_key(url: str | None) -> str:
    host, _ = _host_path(url)
    return host or "unknown"
