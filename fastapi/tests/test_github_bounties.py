from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.ingestion.sources import GitHubBountiesSource
from app.integrations.github_bounties import (
    _extract_bounty_amount,
    fetch_github_bounties,
)


class GitHubBountiesTests(unittest.IsolatedAsyncioTestCase):
    def test_extract_bounty_amount(self) -> None:
        self.assertEqual(_extract_bounty_amount("Fix auth bug - $500 bounty"), 500.0)
        self.assertEqual(_extract_bounty_amount("Bounty: $1,250.50"), 1250.5)
        self.assertIsNone(_extract_bounty_amount("No price here"))
        self.assertIsNone(_extract_bounty_amount("Small $5 tip"))

    async def test_fetch_github_bounties_success(self) -> None:
        mock_payload = {
            "total_count": 1,
            "items": [
                {
                    "id": 99887766,
                    "title": "Build FastAPI GraphQL adapter [$750]",
                    "body": "We need a contractor to build a FastAPI adapter. $750 reward.",
                    "html_url": "https://github.com/acme/project/issues/42",
                    "created_at": "2026-11-05T10:00:00Z",
                    "repository_url": "https://api.github.com/repos/acme/project",
                    "labels": [
                        {"name": "bounty"},
                        {"name": "contract"},
                        {"name": "python"},
                    ],
                    "user": {"login": "maintainer"},
                    "comments": 3,
                }
            ],
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload

        with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_resp)):
            candidates = await fetch_github_bounties(limit=10, query="fastapi")

        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c.source_name, "github_bounties")
        self.assertEqual(c.source_id, "99887766")
        self.assertEqual(c.company, "acme/project")
        self.assertEqual(c.budget_min, 750.0)
        self.assertEqual(c.budget_max, 750.0)
        self.assertIn("contract", c.metadata["tags"])
        self.assertIn("github", c.metadata["tags"])

    async def test_fetch_github_bounties_handles_api_error(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 403

        with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_resp)):
            candidates = await fetch_github_bounties(limit=5)
        self.assertEqual(candidates, [])

    async def test_github_bounties_source_loader(self) -> None:
        source = GitHubBountiesSource()
        self.assertEqual(source.name, "github_bounties")

        with patch(
            "app.integrations.github_bounties.fetch_github_bounties",
            AsyncMock(return_value=[]),
        ) as mock_fetch:
            res = await source.fetch(limit=15, query="python")
            self.assertEqual(res, [])
            mock_fetch.assert_called_once_with(limit=15, query="python")

