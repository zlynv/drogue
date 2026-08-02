"""Thread safety tests for drogue algorithms.

These tests verify that drogue's rate limiting algorithms are thread-safe
under concurrent access. Many Python rate limiting libraries are broken
under multithreading (e.g., tomasbasham/ratelimit allows 2x the limit).

drogue uses threading.RLock and CAS (compare_and_swap) operations
to ensure thread safety.
"""
from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from drogue.core.algorithms import (
    FixedWindowAlgorithm,
    GCRAAlgorithm,
    LeakyBucketAlgorithm,
    SlidingWindowAlgorithm,
    TokenBucketAlgorithm,
)
from drogue.core.storage.memory import MemoryStorage


class TestTokenBucketThreadSafety:
    """Token Bucket must not exceed limit under concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_acquire_respects_limit(self) -> None:
        storage = MemoryStorage()
        algo = TokenBucketAlgorithm(storage=storage, limit=100, window=10.0)
        key = "thread-test"

        results: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(algo.acquire(key))
                with lock:
                    results.append(result.allowed)
            finally:
                loop.close()

        # Launch 200 concurrent requests against limit of 100
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(worker) for _ in range(200)]
            for f in futures:
                f.result()

        allowed_count = sum(results)
        # Should allow exactly 100 (or very close due to timing)
        assert allowed_count <= 100, f"Exceeded limit: {allowed_count}/200 allowed"
        assert allowed_count >= 90, f"Too few allowed: {allowed_count}/200"

    @pytest.mark.asyncio
    async def test_sequential_acquire_no_leak(self) -> None:
        storage = MemoryStorage()
        algo = TokenBucketAlgorithm(storage=storage, limit=10, window=1.0)
        key = "leak-test"

        # Exhaust limit
        for _ in range(10):
            result = await algo.acquire(key)
            assert result.allowed is True

        # 11th should be denied
        result = await algo.acquire(key)
        assert result.allowed is False


class TestSlidingWindowThreadSafety:
    """Sliding Window must not exceed limit under concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_acquire_respects_limit(self) -> None:
        storage = MemoryStorage()
        algo = SlidingWindowAlgorithm(storage=storage, limit=50, window=10.0)
        key = "sw-thread-test"

        results: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(algo.acquire(key))
                with lock:
                    results.append(result.allowed)
            finally:
                loop.close()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker) for _ in range(100)]
            for f in futures:
                f.result()

        allowed_count = sum(results)
        assert allowed_count <= 50, f"Exceeded limit: {allowed_count}/100 allowed"


class TestFixedWindowThreadSafety:
    """Fixed Window must not exceed limit under concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_acquire_respects_limit(self) -> None:
        storage = MemoryStorage()
        algo = FixedWindowAlgorithm(storage=storage, limit=50, window=10.0)
        key = "fw-thread-test"

        results: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(algo.acquire(key))
                with lock:
                    results.append(result.allowed)
            finally:
                loop.close()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker) for _ in range(100)]
            for f in futures:
                f.result()

        allowed_count = sum(results)
        assert allowed_count <= 50, f"Exceeded limit: {allowed_count}/100 allowed"


class TestGCRAThreadSafety:
    """GCRA must not exceed limit under concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_acquire_respects_limit(self) -> None:
        storage = MemoryStorage()
        algo = GCRAAlgorithm(storage=storage, limit=50, window=10.0)
        key = "gcra-thread-test"

        results: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(algo.acquire(key))
                with lock:
                    results.append(result.allowed)
            finally:
                loop.close()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker) for _ in range(100)]
            for f in futures:
                f.result()

        allowed_count = sum(results)
        # GCRA is smoother, may allow slightly fewer due to emission interval
        assert allowed_count <= 55, f"Exceeded limit: {allowed_count}/100 allowed"
        assert allowed_count >= 40, f"Too few allowed: {allowed_count}/100"


class TestLeakyBucketThreadSafety:
    """Leaky Bucket must not exceed limit under concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_acquire_respects_limit(self) -> None:
        storage = MemoryStorage()
        algo = LeakyBucketAlgorithm(storage=storage, limit=50, window=10.0)
        key = "lb-thread-test"

        results: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(algo.acquire(key))
                with lock:
                    results.append(result.allowed)
            finally:
                loop.close()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker) for _ in range(100)]
            for f in futures:
                f.result()

        allowed_count = sum(results)
        assert allowed_count <= 55, f"Exceeded limit: {allowed_count}/100 allowed"
        assert allowed_count >= 40, f"Too few allowed: {allowed_count}/100"


class TestNoDoubleConsume:
    """Verify no double-consume bugs under thread contention."""

    @pytest.mark.asyncio
    async def test_token_bucket_single_token_per_request(self) -> None:
        storage = MemoryStorage()
        algo = TokenBucketAlgorithm(storage=storage, limit=5, window=10.0)
        key = "double-consume"

        # Exhaust all tokens
        for _ in range(5):
            result = await algo.acquire(key)
            assert result.allowed is True

        # All concurrent requests should be denied
        results: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(algo.acquire(key))
                with lock:
                    results.append(result.allowed)
            finally:
                loop.close()

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker) for _ in range(10)]
            for f in futures:
                f.result()

        # None should be allowed since tokens are exhausted
        allowed_count = sum(results)
        assert allowed_count == 0, f"Double consume detected: {allowed_count}/10 allowed"
