# Protection API

## TrustManager

```python
from drogue.protection.trust import TrustManager, TrustLevel

manager = TrustManager(
    max_fingerprints=100000,
    trusted_ttl=14400.0,    # 4 hours
    standard_ttl=1800.0,    # 30 minutes
    score_threshold_trusted=0.2,
    score_threshold_standard=0.5,
)

# Update trust score (0.0 = fully trusted, 1.0 = fully suspicious)
level = manager.update("fingerprint_abc", score=0.1)
# TrustLevel.TRUSTED (score < 0.2)

# Check trust level
level = manager.check("fingerprint_abc")

# Get state
state = manager.get_state("fingerprint_abc")
# TrustState(level=TrustLevel.STANDARD, score=0.5, ...)

# Check by level
assert manager.is_trusted("fingerprint_abc") == True
assert manager.is_banned("fingerprint_abc") == False

# Manual ban
manager.ban("fingerprint_abc")

# Poison (mark as threat)
manager.poison("fingerprint_abc")

# Stats
stats = manager.get_stats()
```

## ProgressiveBanManager

```python
from drogue.protection.ban import ProgressiveBanManager

manager = ProgressiveBanManager(
    threshold=5,           # violations before ban
    window=300.0,          # violation window (seconds)
    max_violations=20,
    escalation=[0, 60, 600, 3600, 86400],  # durations per level
)

# Record a violation
count = manager.record_violation("192.168.1.1")

# Check ban status
is_banned = manager.is_banned("192.168.1.1")

# Get ban details
ban = manager.get_ban("192.168.1.1")
# BanEntry(key='192.168.1.1', level=1, banned_at=..., expires_at=..., violation_count=5)

level = manager.get_ban_level("192.168.1.1")
retry_after = manager.get_retry_after("192.168.1.1")

# Clear
manager.clear_ban("192.168.1.1")
manager.clear_all()
```

## CircuitBreaker

```python
from drogue.protection.circuit import CircuitBreaker

breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30.0,
    jitter=0.2,
    half_open_max_calls=1,
)

# Check if request is allowed
if breaker.allow_request():
    try:
        result = do_work()
        breaker.record_success()
    except Exception:
        breaker.record_failure()

# Get status
status = breaker.get_status()
# {"state": "closed", "failure_count": 0, ...}

# Manual reset
breaker.reset()
```

## DDoSDetector

```python
from drogue.protection.ddos import DDoSDetector

detector = DDoSDetector(
    window=60.0,
    z_threshold=3.0,
    min_clients=10,
    bucket_size=1.0,
    max_clients=10000,
)

# Record HTTP traffic
detector.record("192.168.1.1")

# Record WebSocket traffic
detector.record_ws("client_abc")

# Check anomalies
is_anomalous = detector.is_anomalous("192.168.1.1")
is_http = detector.is_http_anomalous("192.168.1.1")
is_ws = detector.is_ws_anomalous("client_abc")

# Get rates
rate = detector.get_client_rate("192.168.1.1")
global_rate = detector.get_global_rate()

# Stats
stats = detector.get_stats()
```

## ProbeDetector

```python
from drogue.protection.probes import ProbeDetector

detector = ProbeDetector(
    window=300.0,
    probe_threshold=3,
    min_error_rate=0.5,
    max_time_span=60.0,
    threat_boost=0.3,
    max_clients=10000,
)

# Record requests
detector.record("scanner.ip", "/page1", status_code=200, method="GET")

# Check if client is probing
is_probing = detector.is_probing("scanner.ip")

# Get signal details
signal = detector.get_signal("scanner.ip")

# Threat boost (0.0 to 1.0)
boost = detector.get_threat_boost("scanner.ip")

# Cleanup
detector.clear_client("scanner.ip")
detector.clear_all()
```

## CIDRFilter

```python
from drogue.protection.cidr import CIDRFilter

cidr = CIDRFilter(
    allowlist=["192.168.0.0/16"],
    denylist=["185.220.101.0/24"],
)

# Add/remove
cidr.add_to_allowlist("10.0.0.0/8")
cidr.add_to_denylist("2001:db8::/32")
cidr.remove_from_allowlist("10.0.0.0/8")

# Check
is_allowed = cidr.is_allowed("192.168.1.1")
is_denied = cidr.is_denied("185.220.101.50")

# Load from file
count = cidr.load_from_file("blocked_ips.txt", list_type="denylist")

# Stats
stats = cidr.get_stats()
```

## AdaptiveRateLimiter

```python
from drogue.protection.adaptive import AdaptiveRateLimiter

limiter = AdaptiveRateLimiter(
    cpu_threshold=0.8,
    memory_threshold=0.8,
    latency_threshold=1.0,
    check_interval=5.0,
)

# Get effective limit under load
effective = limiter.get_effective_limit(base_limit=1000)

# Record latency for adaptive scaling
limiter.record_latency(0.05)

# Get current metrics
metrics = limiter.get_metrics()
# {"cpu_usage": 65.2, "memory_usage": 72.1, ...}
```
