"""Lead quality: page-type classifier rejects boards, hubs, listings, spam hosts."""

from __future__ import annotations

from types import SimpleNamespace

from backend.application.services.page_type import (
    PAGE_TYPE_BOARD_INDEX,
    PAGE_TYPE_CAREERS_HUB,
    PAGE_TYPE_FULL_TIME,
    PAGE_TYPE_JOB_POST,
    PAGE_TYPE_LISTICLE,
    PAGE_TYPE_NON_DEV,
    PAGE_TYPE_SPAM_HOST,
    classify_page_type,
    is_non_opportunity_noise,
)
from backend.application.services.ranking.diversity import diversify
from backend.application.services.ranking.explanation import ScoreExplanation
from backend.application.services.ranking.pipeline import RankedMatch


def _ranked(job_id: int, title: str, url: str, score: float) -> RankedMatch:
    job = SimpleNamespace(
        id=job_id,
        title=title,
        company="Acme",
        url=url,
        source_name="serpapi_freelance",
        canonical_id=None,
    )
    return RankedMatch(
        job=job,  # type: ignore[arg-type]
        score=score,
        fit_score=score,
        matched_keywords=[],
        reasons=[],
        freshness_score=0.5,
        client_quality_score=0.5,
        red_flags=[],
        explanation=ScoreExplanation(score_version="weighted_v1", fit_score=score),
        score_version="weighted_v1",
        retrieval_path="sql",
    )


def test_rejects_named_boards_and_aggregators():
    samples = [
        ("Working Nomads", "https://www.workingnomads.com/jobs"),
        ("Just Join IT", "https://justjoin.it/"),
        ("CWJobs search", "https://www.cwjobs.co.uk/jobs/python"),
        ("4 Day Week", "https://4dayweek.io/remote-jobs"),
        ("React Jobs", "https://reactjobs.io/"),
        ("Weekday", "https://weekday.works/"),
    ]
    for title, url in samples:
        assert classify_page_type(title, url=url) == PAGE_TYPE_BOARD_INDEX
        assert is_non_opportunity_noise(title, url=url)


def test_rejects_thin_recruiter_and_aggregator_hosts():
    """Desk feed: drop unjobsapp / Hays / jobgether / Twine / contractoruk / GM / pinpointhq."""
    thin = [
        ("UN Jobs listing", "https://unjobsapp.org/jobs/123"),
        ("Python Developer at HAYS", "https://www.hays.co.uk/job/python-123"),
        ("Contract role at HAYS", "https://djangojob.com/job/hays-python"),
        ("Remote React role", "https://jobgether.com/offer/abc123"),
        (
            "Freelance and remote Full stack developers jobs | Twine",
            "https://www.twine.net/jobs/full-stack-developers",
        ),
        (
            "Infrastructure Python Developer",
            "https://www.contractoruk.com/job/462284-infrastructure_python_developer",
        ),
        (
            "Senior Python Developer for Computer Vision at University of Oxford",
            "https://www.jobs.ac.uk/job/DTQ994/senior-python-developer-for-computer-vision",
        ),
        (
            "Senior Software Engineer, Remote | General Motors Careers",
            "https://search-careers.gm.com/en/jobs/jr-202609267/senior-software-engineer",
        ),
        (
            "Senior Backend Engineer - Remote - USA | ProphetX Careers",
            "https://prophetexchange.pinpointhq.com/postings/6f920262-6974-49c7-b6ee-f584edeafe82",
        ),
        ("NY State Contract Reporter", "https://www.nyscr.ny.gov/contracts"),
        ("IT jobs search", "https://www.jobserve.com/gb/en/JobSearch.aspx"),
        ("Notify careers board", "https://notify.careers/jobs"),
        ("JobMail listing", "https://www.jobmail.co.za/jobs"),
        ("IT Job Board UK", "https://www.itjobboard.co.uk/jobs"),
        (
            "React Project Finder | Optimize Upwork Search",
            "https://vollna.com/react-project-finder",
        ),
        ("Upwork React gig", "https://www.upwork.com/jobs/~01abc"),
        (
            "Full-Stack Developer for Language Exchange Chat Room",
            "https://www.workana.com/job/full-stack-developer-for-language-exchange-chat-room",
        ),
        (
            "Sr Software Engineer I - Enterprise Architecture - American Express",
            "https://egug.fa.us2.oraclecloud.com/hcmui/candidateexperience/en/sites/cx_1/job/123",
        ),
        (
            "Senior Python + Flutter Developer (Immediate Joiner)",
            "https://www.pagaarindia.com/jobs/senior-python-flutter-developer-immediate-joiner",
        ),
    ]
    for title, url in thin:
        assert is_non_opportunity_noise(title, url=url), (title, url)


def test_rejects_careers_hubs_without_deep_posting_path():
    assert (
        classify_page_type(
            "Careers at Applied Materials",
            url="https://jobs.appliedmaterials.com/",
        )
        == PAGE_TYPE_CAREERS_HUB
    )
    assert (
        classify_page_type(
            "Jobs at NatWest",
            url="https://jobs.natwestgroup.com/search",
        )
        == PAGE_TYPE_CAREERS_HUB
    )


def test_rejects_listing_page_titles():
    assert is_non_opportunity_noise(
        "Jobs in London — 120+ jobs",
        url="https://example-corp.com/careers",
    )
    assert is_non_opportunity_noise(
        "Search our job opportunities",
        url="https://example-corp.com/join",
    )
    assert is_non_opportunity_noise(
        "Careers & Recruitment",
        url="https://example-corp.com/hr",
    )


def test_rejects_spam_free_hosts_and_non_dev_full_time():
    assert (
        classify_page_type("Dev gig", url="https://cool-project.wuaze.com/job")
        == PAGE_TYPE_SPAM_HOST
    )
    assert (
        classify_page_type(
            "Customer Support Specialist",
            url="https://acme.com/jobs/support-1",
        )
        == PAGE_TYPE_NON_DEV
    )
    assert (
        classify_page_type(
            "Full-time Staff Software Engineer",
            description="Permanent employee role with 401k and PTO",
            url="https://acme.com/jobs/fte-engineer-xyz789",
        )
        == PAGE_TYPE_FULL_TIME
    )


def test_keeps_specific_contract_posting():
    assert (
        classify_page_type(
            "Freelance FastAPI Backend (3 months)",
            description="Contract remote role for a Python developer",
            url="https://boards.greenhouse.io/acme/jobs/1234567",
        )
        == PAGE_TYPE_JOB_POST
    )
    assert not is_non_opportunity_noise(
        "Freelance FastAPI Backend (3 months)",
        "Contract remote role for a Python developer",
        "https://boards.greenhouse.io/acme/jobs/1234567",
    )


def test_rejects_starterindex_even_with_stale_job_post_enrichment():
    assert is_non_opportunity_noise(
        "27 Next.js Boilerplates and Starter Kits",
        url="https://www.starterindex.com/nextjs",
        enrichment={"page_type": "job_post"},
    )
    assert is_non_opportunity_noise(
        "13 FastAPI Boilerplates and Starter Kits",
        url="https://www.starterindex.com/fastapi",
        enrichment={"page_type": "job_post"},
    )
    assert is_non_opportunity_noise(
        "27 Python, Typescript SaaS Boilerplates and Starter Kits",
        url="https://www.starterindex.com/python-typescript",
        enrichment={"page_type": "job_post"},
    )


def test_rules_win_over_stale_enrichment_for_deployed_noise():
    """Deployed sample leads had enrichment.page_type=job_post on hubs/boards."""
    noisy = [
        ("Technology Careers | UBS Global", "https://jobs.ubs.com/careers"),
        ("USAJOBS - Search", "https://www.usajobs.gov/Search/Results"),
        (
            "1,040 IT & Technology Contract Jobs — November 2026 | Contractor UK",
            "https://www.contractoruk.com/contract_jobs/",
        ),
        (
            "Careers and Benefits - Motorola Solutions",
            "https://www.motorolasolutions.com/en_us/about/careers.html",
        ),
        ("Search Jobs | Page 7 - CalOpps", "https://www.calopps.org/search"),
        (
            "Washington Suburban Sanitary Commission Wssc Bids, RFPs ...",
            "https://marylandbids.com/foo",
        ),
        (
            "Open vacancies | Europol",
            "https://www.europol.europa.eu/careers-procurement/vacancies",
        ),
        (
            "mwaa.com - Current Contracting Opportunities",
            "https://www.mwaa.com/business/contracting",
        ),
    ]
    for title, url in noisy:
        assert is_non_opportunity_noise(
            title, url=url, enrichment={"page_type": "job_post"}
        ), title


def test_rejects_starterindex_listicle_and_coding_job_board():
    assert is_non_opportunity_noise(
        "27 Next.js Boilerplates and Starter Kits",
        url="https://www.starterindex.com/nextjs",
    )
    assert (
        classify_page_type("Browse jobs", url="https://codingjobboard.com/")
        == PAGE_TYPE_BOARD_INDEX
    )
    assert (
        classify_page_type("Careers", url="https://career.luxoft.com/")
        == PAGE_TYPE_CAREERS_HUB
    )
    assert (
        classify_page_type("Demo", url="https://app.up.railway.app/jobs/1")
        == PAGE_TYPE_SPAM_HOST
    )


def test_full_time_allowed_only_above_10k_month():
    assert is_non_opportunity_noise(
        "Full-time Staff Software Engineer",
        "Permanent employee role with 401k and PTO. Salary $8k/month.",
        "https://acme.com/jobs/fte-engineer-xyz789",
    )
    assert not is_non_opportunity_noise(
        "Full-time Staff Software Engineer",
        "Permanent employee role. Salary $12k/month.",
        "https://acme.com/jobs/fte-engineer-xyz789",
    )
    # Permanent with no salary listed → reject.
    assert is_non_opportunity_noise(
        "Senior Full Stack Developer",
        "Permanent full-time role. Competitive benefits.",
        "https://helloworld.example/jobs/senior-fs-abc123",
    )
    # High annual salary clears the $10k/mo bar.
    assert not is_non_opportunity_noise(
        "Senior Engineer",
        "Full-time permanent. Salary $150,000–$180,000 per year.",
        "https://foxley.example/jobs/senior-eng-xyz789",
    )


def test_rejects_board_indexes_and_non_posting_hosts():
    assert (
        classify_page_type(
            "Python + FastAPI Developer",
            url="https://builtin.com/job/python-fastapi/10820132",
        )
        == PAGE_TYPE_LISTICLE
    )
    assert is_non_opportunity_noise(
        "Full Stack Developer",
        url="https://aplin.com/job/61318990-full-stack-developer-3-canada-remote",
    )
    assert is_non_opportunity_noise(
        "Sr. Software Engineer",
        url="https://www.edtech.com/jobs/sr-software-engineer-18328",
    )
    assert is_non_opportunity_noise(
        "Palmetto GBA",
        "Agency homepage",
        "https://dmepdac.com/",
    )
    assert is_non_opportunity_noise(
        "Senior Full Stack Developer",
        url="https://www.helloworld.rs/posao/Senior-Full-Stack/739480",
    )
    assert is_non_opportunity_noise(
        "Job : Xpertise Recruitment",
        url="https://www.xpertise-recruitment.com/jobs/job/15398/technical-lead",
    )
    assert is_non_opportunity_noise(
        "Remote Chemistry AI Training Jobs | OpenTrain AI",
        url="https://www.opentrain.ai/jobs/domain/chemistry",
    )
    assert (
        classify_page_type(
            "Platform Engineer",
            url="https://cba.wd3.myworkdayjobs.com/en-US/CommBank_Careers",
        )
        == PAGE_TYPE_CAREERS_HUB
    )
    # Deep Workday job posting kept.
    assert (
        classify_page_type(
            "Platform Engineer",
            description="Contract remote role for a Python developer",
            url="https://cba.wd3.myworkdayjobs.com/en-US/CommBank_Careers/job/Sydney/Platform-Engineer_REQ268046-1",
        )
        == PAGE_TYPE_JOB_POST
    )
    assert is_non_opportunity_noise(
        "USAJOBS - Job Announcement",
        url="https://tech.usajobs.gov/job/865142100",
    )
    assert is_non_opportunity_noise(
        "Technical Curriculum Developer - AI Agents at TrulyHired - LXD Guild",
        url="https://lxdmarketplace.lxdguild.com/jobs/technical-curriculum-developer-ai-agents-ec21efb6",
    )


def test_domain_cap_keeps_exactly_one_per_domain():
    same_domain = [
        _ranked(1, "Role A", "https://9am.works/jobs/a", 0.9),
        _ranked(2, "Role B", "https://9am.works/jobs/b", 0.8),
    ]
    out = diversify(same_domain, max_per_domain=1)
    assert len(out) == 1
    assert out[0].job.id == 1

    distinct = [
        _ranked(
            1,
            "React Contract",
            "https://careers.acme.com/jobs/react-contract-abc123",
            0.9,
        ),
        _ranked(
            2,
            "Python Contract",
            "https://careers.acme.com/jobs/python-contract-def456",
            0.8,
        ),
    ]
    out2 = diversify(distinct, max_per_domain=1)
    assert len(out2) == 1
