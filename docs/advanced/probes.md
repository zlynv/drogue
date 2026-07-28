# Probe Detection

## Overview

Probe Detection identifies reconnaissance patterns that appear 30-120 seconds before the main attack flood.

## How It Works

Attackers often probe endpoints before the main flood:

- 3-5 requests to `/api/login` from each bot
- 404 scans for hidden endpoints
- Small credential stuffing tests

These are below any rate limit threshold but create detectable patterns in aggregate.

## Usage

```python
from drogue.protection.probes import ProbeDetector

detector = ProbeDetector(
    window=300.0,        # 5 minute window
    probe_threshold=3,   # 3 requests = probe signal
    min_error_rate=0.5,  # 50% errors = probe
    max_time_span=60.0,  # All within 1 minute
    threat_boost=0.3,    # Boost threat score by 0.3
)

# Record each request
detector.record("192.168.1.1", "/api/login", 401)

# Check if probing
if detector.is_probing("192.168.1.1"):
    boost = detector.get_threat_boost("192.168.1.1")
```

## Probe Signals

A client is detected as probing when:

1. **Many unique paths** -- 3+ different endpoints in short time
2. **High error rate** -- 50%+ of requests return 4xx/5xx
3. **Short time span** -- All requests within 1 minute

## Example

**Normal user:**

```
GET /api/data -> GET /api/data -> GET /api/data
(same endpoint, regular intervals)
```

**Probe pattern:**

```
GET /api/login -> GET /admin -> GET /wp-login.php -> GET /.env -> GET /api/v1/users
(scattered endpoints, rapid fire, 404s)
```

## Configuration

```python
detector = ProbeDetector(
    window=300.0,              # Time window (seconds)
    probe_threshold=3,         # Minimum requests to consider probe
    min_error_rate=0.5,        # Minimum error rate to flag
    max_time_span=60.0,        # Maximum time span for probe
    threat_boost=0.3,          # Threat score boost
    max_clients=10000,         # Maximum clients to track
    cleanup_interval=60.0,     # Cleanup interval (seconds)
)
```

## Integration with drogue

```python
# In the protection pipeline
probe_score = probe_detector.get_threat_boost(client_id)
ddos_score = ddos_detector.analyze(client_id, features)

# Combined threat score
combined = ddos_score + probe_score

if combined > 0.7:
    # Tighten rate limits for this client
    await ban_manager.record_violation(client_id)
```

## Statistics

```python
stats = detector.get_stats()
# {
#     "total_requests": 10000,
#     "probes_detected": 25,
#     "active_probes": 3,
#     "clients_tracked": 500,
# }
```

## Impact

- **Early warning:** 30-120 seconds before attack flood
- **Low overhead:** Only tracks recent requests per client
- **Zero false positives:** Only flags clear probe patterns
