import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from workers.run_scrape import cycle


class RunScrapeTests(unittest.IsolatedAsyncioTestCase):
    async def test_cycle_success(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"total_fetched": 10}
        mock_response.raise_for_status = MagicMock()

        with patch(
            "workers.run_scrape.httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_post:
            result = await cycle(
                api="http://test",
                sources=["remoteok"],
                limit=10,
                notify=False,
                token="fake",
            )

        mock_post.assert_awaited_once()
        self.assertEqual(result["total_fetched"], 10)


if __name__ == "__main__":
    unittest.main()
