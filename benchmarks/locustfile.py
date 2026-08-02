"""Locust load test for drogue FastAPI benchmark app.

Tests throughput, latency, and correctness of rate limiting.

Run with:
    locust -f benchmarks/locustfile.py --headless -u 100 -r 10 --run-time 60s -H http://localhost:8000

For correctness testing:
    locust -f benchmarks/locustfile.py --headless -u 200 -r 20 --run-time 300s -H http://localhost:8000
"""
from locust import HttpUser, between, events, task


class RateLimitUser(HttpUser):
    """Simulates users hitting rate-limited endpoints."""

    wait_time = between(0.001, 0.01)

    @task(5)
    def token_bucket(self):
        """Token Bucket endpoint (100/sec limit)."""
        self.client.get("/api/token-bucket")

    @task(3)
    def sliding_window(self):
        """Sliding Window endpoint (100/sec limit)."""
        self.client.get("/api/sliding-window")

    @task(3)
    def fixed_window(self):
        """Fixed Window endpoint (100/sec limit)."""
        self.client.get("/api/fixed-window")

    @task(2)
    def heavy(self):
        """Medium-frequency endpoint (50/sec limit)."""
        self.client.get("/api/heavy")

    @task(1)
    def free(self):
        """Unlimited endpoint (no rate limit)."""
        self.client.get("/api/free")


@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    """Print summary statistics on exit."""
    stats = environment.runner.stats
    total_requests = stats.total.num_requests
    total_failures = stats.total.num_failures
    avg_response_time = stats.total.avg_response_time

    duration = environment.runner.stats.last_request_timestamp - environment.runner.stats.start_time
    rps = total_requests / max(1, duration)

    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Total requests:    {total_requests:,}")
    print(f"Total failures:    {total_failures:,}")
    print(f"Avg response time: {avg_response_time:.1f}ms")
    print(f"Requests/sec:      {rps:.1f}")
    print("=" * 60)
