"""Benchmark drogue rate limiting performance."""
import asyncio
import time
import statistics
from drogue.core.algorithms.token_bucket import TokenBucketAlgorithm
from drogue.core.algorithms.sliding_window import SlidingWindowAlgorithm
from drogue.core.algorithms.fixed_window import FixedWindowAlgorithm
from drogue.core.storage.memory import MemoryStorage


async def benchmark_algorithm(name, algo, key, iterations=100_000):
    """Benchmark an algorithm's acquire method."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        await algo.acquire(key)
        end = time.perf_counter_ns()
        times.append(end - start)

    times.sort()
    median_ns = statistics.median(times)
    p95_ns = times[int(iterations * 0.95)]
    p99_ns = times[int(iterations * 0.99)]

    print(f"  {name:25s} median={median_ns/1000:.1f}us  p95={p95_ns/1000:.1f}us  p99={p99_ns/1000:.1f}us")
    return median_ns


async def benchmark_throughput(algo, key, duration=2.0):
    """Benchmark requests per second."""
    count = 0
    start = time.perf_counter()
    while time.perf_counter() - start < duration:
        await algo.acquire(key)
        count += 1
    elapsed = time.perf_counter() - start
    rps = count / elapsed
    return rps


async def main():
    storage = MemoryStorage()
    await storage.initialize()

    print("=== Algorithm Latency (100K iterations) ===\n")

    tb = TokenBucketAlgorithm(storage=storage, limit=1_000_000, window=60.0)
    sw = SlidingWindowAlgorithm(storage=storage, limit=1_000_000, window=60.0)
    fw = FixedWindowAlgorithm(storage=storage, limit=1_000_000, window=60.0)

    await benchmark_algorithm("Token Bucket", tb, "bench_key")
    await benchmark_algorithm("Sliding Window", sw, "bench_key_sw")
    await benchmark_algorithm("Fixed Window", fw, "bench_key_fw")

    print("\n=== Throughput (2 seconds each) ===\n")

    tb2 = TokenBucketAlgorithm(storage=storage, limit=10_000_000, window=60.0)
    sw2 = SlidingWindowAlgorithm(storage=storage, limit=10_000_000, window=60.0)
    fw2 = FixedWindowAlgorithm(storage=storage, limit=10_000_000, window=60.0)

    rps_tb = await benchmark_throughput(tb2, "tp_tb")
    rps_sw = await benchmark_throughput(sw2, "tp_sw")
    rps_fw = await benchmark_throughput(fw2, "tp_fw")

    print(f"  Token Bucket:    {rps_tb:,.0f} req/s")
    print(f"  Sliding Window:  {rps_sw:,.0f} req/s")
    print(f"  Fixed Window:    {rps_fw:,.0f} req/s")

    print("\n=== Memory per key ===\n")
    import sys
    # Each key stores a tuple of 2 floats + metadata
    print(f"  Tuple overhead: {sys.getsizeof((0.0, 0.0))} bytes")
    print(f"  (Approx 150 bytes per key with dict overhead)")


if __name__ == "__main__":
    asyncio.run(main())
