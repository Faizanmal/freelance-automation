"""Reddit hiring hunter: [Hiring] only, skip [For Hire], OAuth fetch mapping."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.integrations import reddit_hiring


class RedditHiringFilterTests(unittest.TestCase):
    def test_accepts_hiring_tag(self) -> None:
        self.assertTrue(reddit_hiring.is_hiring_post("[Hiring] Python contractor"))

    def test_rejects_for_hire(self) -> None:
        self.assertFalse(
            reddit_hiring.is_hiring_post("[For Hire] Available Python dev")
        )
        self.assertFalse(reddit_hiring.is_hiring_post("[ForHire] Available"))

    def test_rejects_without_hiring_tag(self) -> None:
        self.assertFalse(reddit_hiring.is_hiring_post("Need a developer ASAP"))


class RedditHiringFetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_not_configured_raises(self) -> None:
        with patch("app.integrations.reddit_hiring.get_settings") as settings:
            settings.return_value.reddit_client_id = None
            settings.return_value.reddit_client_secret = None
            with self.assertRaises(reddit_hiring.SourceNotConfiguredError):
                await reddit_hiring.search_hiring(limit=5)

    async def test_maps_hiring_posts_and_skips_for_hire(self) -> None:
        listing = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc",
                            "title": "[Hiring] FastAPI freelance",
                            "selftext": "Need a contractor this month.",
                            "permalink": "/r/forhire/comments/abc/hiring_fastapi/",
                            "author": "client1",
                            "created_utc": 1_700_000_000,
                        }
                    },
                    {
                        "data": {
                            "id": "def",
                            "title": "[For Hire] Python expert",
                            "selftext": "I am available",
                            "permalink": "/r/forhire/comments/def/for_hire/",
                            "author": "seller",
                            "created_utc": 1_700_000_100,
                        }
                    },
                ]
            }
        }
        token_response = MagicMock()
        token_response.raise_for_status = MagicMock()
        token_response.json.return_value = {"access_token": "tok"}

        listing_response = MagicMock()
        listing_response.status_code = 200
        listing_response.json.return_value = listing
        listing_response.text = ""

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=token_response)
        mock_client.get = AsyncMock(return_value=listing_response)

        with (
            patch("app.integrations.reddit_hiring.get_settings") as settings,
            patch(
                "app.integrations.reddit_hiring.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            settings.return_value.reddit_client_id = "id"
            settings.return_value.reddit_client_secret = "secret"
            settings.return_value.reddit_user_agent = "test-agent"
            settings.return_value.reddit_subreddits = "forhire"
            rows = await reddit_hiring.search_hiring(limit=10)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "[Hiring] FastAPI freelance")
        self.assertEqual(
            rows[0]["url"],
            "https://www.reddit.com/r/forhire/comments/abc/hiring_fastapi/",
        )
        self.assertIn("hiring", rows[0]["metadata"]["tags"])


if __name__ == "__main__":
    unittest.main()
