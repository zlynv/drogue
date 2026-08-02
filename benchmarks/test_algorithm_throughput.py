"""Throughput comparison benchmark for all 5 algorithms.

Runs all algorithms in a single test for fair comparison.
Run with: pytest benchmarks/test_algorithm_throughput.py -v --benchmark-only
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
ITERATIONS = 10000


@pytest.fixture
def storage():
    return MemoryStorage()


def _bench(algo_class, storage, key="bench"):
    algo = algo_class(storage=storage, limit=LIMIT, window=WINDOW)

    async def _run():
        for _ in range(ITERATIONS):
            await algo.acquire(key)
    asyncio.run(_run())


def test_token_bucket_throughput(storage, benchmark):
    benchmark.pedantic(_bench, args=(TokenBucketAlgorithm, storage), rounds=10, warmup_rounds=2)


def test_sliding_window_throughput(storage, benchmark):
    benchmark.pedantic(_bench, args=(SlidingWindowAlgorithm, storage), rounds=10, warmup_rounds=2)


def test_fixed_window_throughput(storage, benchmark):
    benchmark.pedantic(_bench, args=(FixedWindowAlgorithm, storage), rounds=10, warmup_rounds=2)


def test_gcra_throughput(storage, benchmark):
    benchmark.pedantic(_bench, args=(GCRAAlgorithm, storage), rounds=10, warmup_rounds=2)


def test_leaky_bucket_throughput(storage, benchmark):
    benchmark.pedantic(_bench, args=(LeakyBucketAlgorithm, storage), rounds=10, warmup_rounds=2)
