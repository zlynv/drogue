"""Memory usage benchmark for all 5 algorithms.

Measures bytes per key for each algorithm with 100K unique keys.
Run with: pytest benchmarks/test_memory.py -v --benchmark-only
"""
import asyncio
import tracemalloc

from drogue.core.algorithms.fixed_window import FixedWindowAlgorithm
from drogue.core.algorithms.gcra import GCRAAlgorithm
from drogue.core.algorithms.leaky_bucket import LeakyBucketAlgorithm
from drogue.core.algorithms.sliding_window import SlidingWindowAlgorithm
from drogue.core.algorithms.token_bucket import TokenBucketAlgorithm
from drogue.core.storage.memory import MemoryStorage

LIMIT = 100
WINDOW = 60.0
NUM_KEYS = 100_000


def _measure_memory(algo_class):
    storage = MemoryStorage()
    algo = algo_class(storage=storage, limit=LIMIT, window=WINDOW)

    async def _populate():
        for i in range(NUM_KEYS):
            await algo.acquire(f"key:{i}")

    tracemalloc.start()
    before = tracemalloc.get_traced_memory()
    asyncio.run(_populate())
    after = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    used = after[0] - before[0]
    per_key = used / NUM_KEYS
    return used, per_key


def test_token_bucket_memory(benchmark):
    used, per_key = benchmark.pedantic(_measure_memory, args=(TokenBucketAlgorithm,), rounds=5, warmup_rounds=1)
    print(f"\n  Token Bucket: {used:,} bytes total, {per_key:.1f} bytes/key")


def test_sliding_window_memory(benchmark):
    used, per_key = benchmark.pedantic(_measure_memory, args=(SlidingWindowAlgorithm,), rounds=5, warmup_rounds=1)
    print(f"\n  Sliding Window: {used:,} bytes total, {per_key:.1f} bytes/key")


def test_fixed_window_memory(benchmark):
    used, per_key = benchmark.pedantic(_measure_memory, args=(FixedWindowAlgorithm,), rounds=5, warmup_rounds=1)
    print(f"\n  Fixed Window: {used:,} bytes total, {per_key:.1f} bytes/key")


def test_gcra_memory(benchmark):
    used, per_key = benchmark.pedantic(_measure_memory, args=(GCRAAlgorithm,), rounds=5, warmup_rounds=1)
    print(f"\n  GCRA: {used:,} bytes total, {per_key:.1f} bytes/key")


def test_leaky_bucket_memory(benchmark):
    used, per_key = benchmark.pedantic(_measure_memory, args=(LeakyBucketAlgorithm,), rounds=5, warmup_rounds=1)
    print(f"\n  Leaky Bucket: {used:,} bytes total, {per_key:.1f} bytes/key")
