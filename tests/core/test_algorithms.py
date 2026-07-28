"""Tests for rate limiting algorithms."""
from __future__ import annotations

import asyncio

import pytest

from drogue.core.algorithms.fixed_window import FixedWindowAlgorithm
from drogue.core.algorithms.sliding_window import SlidingWindowAlgorithm
from drogue.core.algorithms.token_bucket import TokenBucketAlgorithm
from drogue.core.storage.memory import MemoryStorage


class TestTokenBucket:
    """Tests for Token Bucket algorithm."""

    @pytest.fixture
    def storage(self) -> MemoryStorage:
        return MemoryStorage()

    @pytest.fixture
    def algo(self, storage: MemoryStorage) -> TokenBucketAlgorithm:
        return TokenBucketAlgorithm(storage=storage, limit=5, window=1.0)

    @pytest.mark.asyncio
    async def test_first_request_allowed(self, algo: TokenBucketAlgorithm) -> None:
        result = await algo.acquire("user1")
        assert result.allowed is True
        assert result.remaining == 4
        assert result.limit == 5

    @pytest.mark.asyncio
    async def test_exhaust_tokens(self, algo: TokenBucketAlgorithm) -> None:
        # Use all tokens
        for _ in range(5):
            result = await algo.acquire("user1")
            assert result.allowed is True

        # 6th should be denied
        result = await algo.acquire("user1")
        assert result.allowed is False
        assert result.retry_after is not None

    @pytest.mark.asyncio
    async def test_tokens_refill(self, algo: TokenBucketAlgorithm) -> None:
        # Exhaust tokens
        for _ in range(5):
            await algo.acquire("user1")

        # Wait for refill
        await asyncio.sleep(0.5)

        # Should have some tokens back
        result = await algo.acquire("user1")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_separate_keys(self, algo: TokenBucketAlgorithm) -> None:
        # Exhaust user1
        for _ in range(5):
            await algo.acquire("user1")

        # user2 should still be allowed
        result = await algo.acquire("user2")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_cost(self, algo: TokenBucketAlgorithm) -> None:
        result = await algo.acquire("user1", cost=3)
        assert result.allowed is True
        assert result.remaining == 2

    @pytest.mark.asyncio
    async def test_cost_exceeds(self, algo: TokenBucketAlgorithm) -> None:
        result = await algo.acquire("user1", cost=6)
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_peek(self, algo: TokenBucketAlgorithm) -> None:
        result = await algo.peek("user1")
        assert result.allowed is True
        assert result.remaining == 5

        await algo.acquire("user1", cost=2)
        result = await algo.peek("user1")
        assert result.remaining == 3

    @pytest.mark.asyncio
    async def test_reset(self, algo: TokenBucketAlgorithm) -> None:
        for _ in range(5):
            await algo.acquire("user1")

        result = await algo.acquire("user1")
        assert result.allowed is False

        await algo.reset("user1")
        result = await algo.acquire("user1")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_different_keys_independent(self, algo: TokenBucketAlgorithm) -> None:
        # Exhaust user1
        for _ in range(5):
            await algo.acquire("user1")

        # user2 should be unaffected
        result = await algo.acquire("user2")
        assert result.allowed is True
        assert result.remaining == 4


class TestSlidingWindow:
    """Tests for Sliding Window algorithm."""

    @pytest.fixture
    def storage(self) -> MemoryStorage:
        return MemoryStorage()

    @pytest.fixture
    def algo(self, storage: MemoryStorage) -> SlidingWindowAlgorithm:
        return SlidingWindowAlgorithm(storage=storage, limit=5, window=1.0)

    @pytest.mark.asyncio
    async def test_first_request_allowed(self, algo: SlidingWindowAlgorithm) -> None:
        result = await algo.acquire("user1")
        assert result.allowed is True
        assert result.remaining == 4

    @pytest.mark.asyncio
    async def test_exhaust_limit(self, algo: SlidingWindowAlgorithm) -> None:
        for _ in range(5):
            result = await algo.acquire("user1")
            assert result.allowed is True

        result = await algo.acquire("user1")
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_window_slide(self, algo: SlidingWindowAlgorithm) -> None:
        # Exhaust limit
        for _ in range(5):
            await algo.acquire("user1")

        # Wait for window to slide
        await asyncio.sleep(1.1)

        result = await algo.acquire("user1")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_peek(self, algo: SlidingWindowAlgorithm) -> None:
        result = await algo.peek("user1")
        assert result.allowed is True
        assert result.remaining == 5

    @pytest.mark.asyncio
    async def test_reset(self, algo: SlidingWindowAlgorithm) -> None:
        for _ in range(5):
            await algo.acquire("user1")

        await algo.reset("user1")
        result = await algo.acquire("user1")
        assert result.allowed is True


class TestFixedWindow:
    """Tests for Fixed Window algorithm."""

    @pytest.fixture
    def storage(self) -> MemoryStorage:
        return MemoryStorage()

    @pytest.fixture
    def algo(self, storage: MemoryStorage) -> FixedWindowAlgorithm:
        return FixedWindowAlgorithm(storage=storage, limit=5, window=1.0)

    @pytest.mark.asyncio
    async def test_first_request_allowed(self, algo: FixedWindowAlgorithm) -> None:
        result = await algo.acquire("user1")
        assert result.allowed is True
        assert result.remaining == 4

    @pytest.mark.asyncio
    async def test_exhaust_limit(self, algo: FixedWindowAlgorithm) -> None:
        for _ in range(5):
            result = await algo.acquire("user1")
            assert result.allowed is True

        result = await algo.acquire("user1")
        assert result.allowed is False
        assert result.retry_after is not None

    @pytest.mark.asyncio
    async def test_window_reset(self, algo: FixedWindowAlgorithm) -> None:
        # Exhaust limit
        for _ in range(5):
            await algo.acquire("user1")

        # Wait for new window
        await asyncio.sleep(1.1)

        result = await algo.acquire("user1")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_peek(self, algo: FixedWindowAlgorithm) -> None:
        result = await algo.peek("user1")
        assert result.allowed is True
        assert result.remaining == 5

    @pytest.mark.asyncio
    async def test_reset(self, algo: FixedWindowAlgorithm) -> None:
        for _ in range(5):
            await algo.acquire("user1")

        await algo.reset("user1")
        result = await algo.acquire("user1")
        assert result.allowed is True


class TestAlgorithmComparison:
    """Compare algorithms across similar scenarios."""

    @pytest.fixture
    def storage(self) -> MemoryStorage:
        return MemoryStorage()

    @pytest.mark.asyncio
    async def test_all_algorithms_basic(self, storage: MemoryStorage) -> None:
        """All algorithms should allow requests within limit."""
        algorithms = [
            TokenBucketAlgorithm(storage, limit=3, window=1.0),
            SlidingWindowAlgorithm(storage, limit=3, window=1.0),
            FixedWindowAlgorithm(storage, limit=3, window=1.0),
        ]

        for algo in algorithms:
            for i in range(3):
                result = await algo.acquire("test_key")
                assert result.allowed is True, f"{algo.__class__.__name__} failed at request {i}"
