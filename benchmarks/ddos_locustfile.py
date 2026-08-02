"""Locust load test for drogue DDoS protection benchmark.

Tests DDoS detection, ban escalation, and circuit breaker under load.

Run with:
    locust -f benchmarks/ddos_locustfile.py --headless -u 100 -r 10 --run-time 60s -H http://localhost:8000
"""
from locust import HttpUser, between, events, task


class NormalUser(HttpUser):
    """Normal users - stay under limits."""
    wait_time = between(0.01, 0.05)
    weight = 4

    @task(5)
    def get_data(self):
        self.client.get("/api/data")

    @task(3)
    def heavy(self):
        self.client.get("/api/heavy")

    @task(2)
    def free(self):
        self.client.get("/api/free")


class AttackerUser(HttpUser):
    """Simulated DDoS attacker - hammers endpoints rapidly."""
    wait_time = between(0.001, 0.005)
    weight = 1

    @task(10)
    def rapid_fire(self):
        """Fire requests as fast as possible."""
        self.client.get("/api/data")

    @task(5)
    def heavy_attack(self):
        """Attack heavy endpoint."""
        self.client.get("/api/heavy")

    @task(3)
    def free_attack(self):
        """Attack free endpoint."""
        self.client.get("/api/free")

    @task(1)
    def check_ban(self):
        """Check if we're banned."""
        self.client.get("/api/ban-check")


class SuperAttackerUser(HttpUser):
    """Super attacker - sends 10x more traffic to trigger DDoS detection."""
    wait_time = between(0.0001, 0.001)
    weight = 1

    @task(20)
    def super_rapid_fire(self):
        """Fire requests extremely fast."""
        self.client.get("/api/data")

    @task(10)
    def super_heavy_attack(self):
        """Attack heavy endpoint."""
        self.client.get("/api/heavy")

    @task(5)
    def super_free_attack(self):
        """Attack free endpoint."""
        self.client.get("/api/free")


@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    stats = environment.runner.stats
    total_requests = stats.total.num_requests
    total_failures = stats.total.num_failures
    avg_response_time = stats.total.avg_response_time
    duration = stats.last_request_timestamp - stats.start_time
    rps = total_requests / max(1, duration)

    print("\n" + "=" * 60)
    print("DDoS BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Total requests:    {total_requests:,}")
    print(f"Total failures:    {total_failures:,}")
    print(f"Failure rate:      {(total_failures/max(1,total_requests)*100):.1f}%")
    print(f"Avg response time: {avg_response_time:.1f}ms")
    print(f"Requests/sec:      {rps:.1f}")
    print("=" * 60)
