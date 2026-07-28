"""Tests for storage backends."""
from __future__ import annotations

import asyncio

import pytest

from drogue.core.storage.memory import MemoryStorage


class TestMemoryStorage:
    """Tests for in-memory storage backend."""

    @pytest.fixture
    def storage(self) -> MemoryStorage:
        return MemoryStorage()

    @pytest.mark.asyncio
    async def test_set_and_get(self, storage: MemoryStorage) -> None:
        await storage.set("key1", 42, ttl=60.0)
        result = await storage.get("key1")
        assert result == 42

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, storage: MemoryStorage) -> None:
        result = await storage.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, storage: MemoryStorage) -> None:
        await storage.set("key1", 1, ttl=60.0)
        assert await storage.exists("key1") is True
        await storage.delete("key1")
        assert await storage.exists("key1") is False

    @pytest.mark.asyncio
    async def test_incr(self, storage: MemoryStorage) -> None:
        result = await storage.incr("counter", window=60.0, amount=1)
        assert result == 1
        result = await storage.incr("counter", window=60.0, amount=3)
        assert result == 4

    @pytest.mark.asyncio
    async def test_incr_new_key(self, storage: MemoryStorage) -> None:
        result = await storage.incr("new_counter", window=60.0, amount=5)
        assert result == 5

    @pytest.mark.asyncio
    async def test_increment_by(self, storage: MemoryStorage) -> None:
        count, ttl = await storage.increment_by("key", 5, window=10.0)
        assert count == 5
        assert ttl > 0 and ttl <= 10.0

        count, ttl = await storage.increment_by("key", 3, window=10.0)
        assert count == 8

    @pytest.mark.asyncio
    async def test_exists(self, storage: MemoryStorage) -> None:
        assert await storage.exists("key") is False
        await storage.set("key", 1, ttl=60.0)
        assert await storage.exists("key") is True

    @pytest.mark.asyncio
    async def test_ttl(self, storage: MemoryStorage) -> None:
        # Non-existent key
        assert await storage.ttl("key") == -2.0

        # Key with TTL
        await storage.set("key", 1, ttl=60.0)
        ttl = await storage.ttl("key")
        assert ttl > 0 and ttl <= 60.0

    @pytest.mark.asyncio
    async def test_expire(self, storage: MemoryStorage) -> None:
        await storage.set("key", 1, ttl=60.0)
        await storage.expire("key", 0.01)  # Very short TTL
        await asyncio.sleep(0.02)
        assert await storage.get("key") is None

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, storage: MemoryStorage) -> None:
        """Test that expired keys are cleaned up."""
        await storage.set("expired", 1, ttl=0.01)
        await storage.set("valid", 1, ttl=60.0)
        await asyncio.sleep(0.02)
        # len() triggers cleanup
        assert len(storage) == 1

    @pytest.mark.asyncio
    async def test_initialize_and_close(self, storage: MemoryStorage) -> None:
        await storage.initialize()
        assert storage._initialized is True
        await storage.close()
        assert storage._initialized is False
