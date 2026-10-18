import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.integrations.freelancer import place_bid


class FreelancerIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_place_bid_success(self) -> None:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={"status": "success", "result": {"id": 1234, "amount": 500}}
        )
        mock_response.raise_for_status = AsyncMock()

        with patch(
            "app.integrations.freelancer._auth_headers",
            return_value={"Authorization": "test-token"},
        ), patch(
            "app.integrations.freelancer.httpx.AsyncClient.post",
            return_value=mock_response,
        ) as mock_post:
            result = await place_bid(
                project_id=1,
                amount=500.0,
                period=7,
                description="Hello",
                milestone_percentage=100,
                bidder_id=42,
            )

        mock_post.assert_awaited_once()
        self.assertEqual(result["id"], 1234)


if __name__ == "__main__":
    unittest.main()
