"""Remaining: Celery availability helper fails closed when broker/workers are down."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from workers.availability import celery_workers_online


class CeleryAvailabilityTests(unittest.TestCase):
    def test_returns_false_when_inspect_raises(self) -> None:
        with patch("workers.app.celery_app") as celery_app:
            celery_app.control.inspect.side_effect = Exception("broker down")
            self.assertFalse(celery_workers_online(timeout=0.01))

    def test_returns_false_when_no_workers_ping(self) -> None:
        inspector = MagicMock()
        inspector.ping.return_value = None
        with patch("workers.app.celery_app") as celery_app:
            celery_app.control.inspect.return_value = inspector
            self.assertFalse(celery_workers_online(timeout=0.01))

    def test_returns_true_when_worker_pings(self) -> None:
        inspector = MagicMock()
        inspector.ping.return_value = {"worker@host": {"ok": "pong"}}
        with patch("workers.app.celery_app") as celery_app:
            celery_app.control.inspect.return_value = inspector
            self.assertTrue(celery_workers_online(timeout=0.01))


if __name__ == "__main__":
    unittest.main()
