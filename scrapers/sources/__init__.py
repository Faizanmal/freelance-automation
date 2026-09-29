"""HTTP + marketplace source adapters."""

from __future__ import annotations

from scrapers.sources.arbeitnow import ArbeitnowScraper
from scrapers.sources.freelancer import FreelancerScraper
from scrapers.sources.himalayas import HimalayasScraper
from scrapers.sources.jobicy import JobicyScraper
from scrapers.sources.remoteok import RemoteOKScraper
from scrapers.sources.remotive import RemotiveScraper
from scrapers.sources.upwork import UpworkScraper

__all__ = [
    "ArbeitnowScraper",
    "FreelancerScraper",
    "HimalayasScraper",
    "JobicyScraper",
    "RemoteOKScraper",
    "RemotiveScraper",
    "UpworkScraper",
]
