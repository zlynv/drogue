"""Function-level latency benchmarks for all 5 algorithms.

Measures pure acquire() call performance without HTTP overhead.
Run with: pytest benchmarks/test_algorithm_latency.py -v --benchmark-only
"""
import asyncio

import pytest

from drogue.core.algorithms.fixed_window import FixedWindowAlgorithm
from drogue.core.algorithms.gcra import GCRAAlgorithm
from drogue.core.algorithms.leaky_bucket import LeakyBucketAlgorithm
from drogue.core.algorithms.sliding_window import SlidingWindowAlgorithm
from drogue.core.algorithms.token_bucket import TokenBucketAlgorithm
from drogue.core.storage.memory import MemoryStorage

LIMIT = 1000
WINDOW = 60.0


@pytest.fixture
def storage():
    return MemoryStorage()


@pytest.fixture
def token_bucket(storage):
    return TokenBucketAlgorithm(storage=storage, limit=LIMIT, window=WINDOW)


@pytest.fixture
def sliding_window(storage):
    return SlidingWindowAlgorithm(storage=storage, limit=LIMIT, window=WINDOW)


@pytest.fixture
def fixed_window(storage):
    return FixedWindowAlgorithm(storage=storage, limit=LIMIT, window=WINDOW)


@pytest.fixture
def gcra(storage):
    return GCRAAlgorithm(storage=storage, limit=LIMIT, window=WINDOW)


@pytest.fixture
def leaky_bucket(storage):
    return LeakyBucketAlgorithm(storage=storage, limit=LIMIT, window=WINDOW)


def _bench_algo(algo, key="bench_key"):
    async def _run():
        for _ in range(10000):
            await algo.acquire(key)
    asyncio.run(_run())


def test_token_bucket_latency(token_bucket, benchmark):
    benchmark.pedantic(_bench_algo, args=(token_bucket,), rounds=10, warmup_rounds=2)


def test_sliding_window_latency(sliding_window, benchmark):
    benchmark.pedantic(_bench_algo, args=(sliding_window,), rounds=10, warmup_rounds=2)


def test_fixed_window_latency(fixed_window, benchmark):
    benchmark.pedantic(_bench_algo, args=(fixed_window,), rounds=10, warmup_rounds=2)


def test_gcra_latency(gcra, benchmark):
    benchmark.pedantic(_bench_algo, args=(gcra,), rounds=10, warmup_rounds=2)


def test_leaky_bucket_latency(leaky_bucket, benchmark):
    benchmark.pedantic(_bench_algo, args=(leaky_bucket,), rounds=10, warmup_rounds=2)
