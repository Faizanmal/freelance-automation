"""Overlap lock behavior with Redis mocked / unavailable."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from workers.locks import overlap_lock


def test_lock_allows_when_redis_unavailable() -> None:
    with patch("workers.locks._sync_redis", return_value=None):
        with overlap_lock("unit-test") as acquired:
            assert acquired is True


def test_lock_skips_when_held() -> None:
    client = MagicMock()
    client.set.return_value = False
    with patch("workers.locks._sync_redis", return_value=client):
        with overlap_lock("unit-test", ttl_seconds=30) as acquired:
            assert acquired is False
    client.delete.assert_not_called()


def test_lock_releases_owned_token() -> None:
    client = MagicMock()
    client.set.return_value = True
    client.get.return_value = None  # overwritten below

    def _set(key, token, nx=True, ex=30):
        client.get.return_value = token
        return True

    client.set.side_effect = _set
    with patch("workers.locks._sync_redis", return_value=client):
        with overlap_lock("unit-test", ttl_seconds=30) as acquired:
            assert acquired is True
    client.delete.assert_called_once()
