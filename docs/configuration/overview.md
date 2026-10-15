# Configuration Overview

## DrogueConfig

All drogue configuration is done through the `DrogueConfig` dataclass.

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    # Defaults
    default_algorithm="token_bucket",
    default_fail_closed=True,
    default_headers=True,
    default_retry_after=True,

    # Proxy handling
    trusted_proxies=["10.0.0.0/8"],
    proxy_header="x-forwarded-for",
    trust_x_real_ip=True,

    # Ban settings
    ban_enabled=True,
    ban_threshold=5,
    ban_window=300.0,
    ban_escalation=[0, 60, 600, 3600, 86400],

    # DDoS detection
    ddos_enabled=True,
    ddos_z_score_threshold=3.0,
    ddos_min_clients=10,
    ddos_window=60.0,

    # Circuit breaker
    circuit_breaker_enabled=True,
    circuit_failure_threshold=5,
    circuit_recovery_timeout=30.0,
    circuit_jitter=0.2,

    # Shadow mode
    shadow_enabled=False,

    # CIDR filtering
    cidr_allowlist=["10.0.0.0/8"],
    cidr_denylist=["192.168.1.100/32"],

    # Adaptive rate limiting
    adaptive_enabled=False,
    adaptive_cpu_threshold=0.8,
    adaptive_memory_threshold=0.8,
    adaptive_latency_threshold=1.0,

    # Storage
    storage_backend="memory",
    redis_url="redis://localhost:6379",

    # Probe detection
    probes_enabled=False,
    probes_retry_after=60.0,

    # Trust fast-path
    trust_enabled=False,
    trust_success_threshold=100,
    trust_limit_multiplier=1.0,

    # Sentinel anomaly detection
    sentinel_enabled=False,
    sentinel_sample_rate=0.01,
    sentinel_block=False,

    # Defense randomization
    randomizer_enabled=False,
    randomizer_session_header="x-session-id",

    # Honeypot trap paths
    honeypot_paths=[],
    honeypot_ban=True,

    # Observability
    metrics_enabled=True,
    logging_enabled=True,
    log_level="warning",
)
```

When detection flags are set on a FastAPI limiter without an explicit
`pipeline=`, the limiter auto-builds a `ProtectionPipeline` holding the
enabled components. Passing your own pipeline always wins; the flags
are then ignored for detection (the limiter still applies the trust
and randomizer limit modifiers from your pipeline's shared instances).

## Configuration Groups

### Behavior

| Setting | Default | Description |
|---------|---------|-------------|
| `default_algorithm` | `token_bucket` | Rate limiting algorithm |
| `default_fail_closed` | `True` | Deny on backend failure |
| `default_headers` | `True` | Inject rate-limit headers |
| `default_retry_after` | `True` | Include Retry-After header |

### Proxy Handling

| Setting | Default | Description |
|---------|---------|-------------|
| `trusted_proxies` | `[]` | Trusted proxy CIDRs. **Forwarded headers (X-Forwarded-For, X-Real-IP) are ONLY honored when the direct peer IP is in this list.** Empty list = headers never trusted. |
| `proxy_header` | `x-forwarded-for` | Header for client IP chain |
| `trust_x_real_ip` | `True` | Trust X-Real-IP header (only when peer is trusted) |

### Ban Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `ban_enabled` | `False` | Enable auto-banning |
| `ban_threshold` | `5` | Violations before ban |
| `ban_window` | `300.0` | Violation window (seconds) |
| `ban_escalation` | `[0, 60, 600, 3600, 86400]` | Ban durations per level |

### DDoS Detection

| Setting | Default | Description |
|---------|---------|-------------|
| `ddos_enabled` | `False` | Enable DDoS detection |
| `ddos_z_score_threshold` | `3.0` | Z-score threshold |
| `ddos_min_clients` | `10` | Minimum clients before detection activates |
| `ddos_window` | `60.0` | Detection window (seconds) |

### Circuit Breaker

| Setting | Default | Description |
|---------|---------|-------------|
| `circuit_breaker_enabled` | `False` | Enable circuit breaker |
| `circuit_failure_threshold` | `5` | Failures before open |
| `circuit_recovery_timeout` | `30.0` | Recovery timeout (seconds) |
| `circuit_jitter` | `0.2` | Jitter to prevent thundering herd |

### CIDR Filtering

| Setting | Default | Description |
|---------|---------|-------------|
| `cidr_allowlist` | `[]` | Only allow these IPs |
| `cidr_denylist` | `[]` | Always block these IPs |

### Adaptive Rate Limiting

| Setting | Default | Description |
|---------|---------|-------------|
| `adaptive_enabled` | `False` | Enable adaptive limits |
| `adaptive_cpu_threshold` | `0.8` | Reduce when CPU > 80% |
| `adaptive_memory_threshold` | `0.8` | Reduce when memory > 80% |
| `adaptive_latency_threshold` | `1.0` | Reduce when p95 > 1s |

### Storage

| Setting | Default | Description |
|---------|---------|-------------|
| `storage_backend` | `memory` | Storage backend (`memory` or `redis`) |
| `redis_url` | `redis://localhost:6379` | Redis connection URL |

Pass a `Storage` to `ProgressiveBanManager(storage=...)` to share ban
state across processes/hosts, and use its `*_async` methods.

### Probe Detection

| Setting | Default | Description |
|---------|---------|-------------|
| `probes_enabled` | `False` | Block clients showing recon patterns (429) |
| `probes_retry_after` | `60.0` | Retry-After for probe blocks |

### Trust Fast-Path

| Setting | Default | Description |
|---------|---------|-------------|
| `trust_enabled` | `False` | Track success streaks toward TRUSTED |
| `trust_success_threshold` | `100` | Consecutive successes before promotion |
| `trust_limit_multiplier` | `1.0` | Limit multiplier for TRUSTED keys (`1.0` = off) |

### Sentinel Anomaly Detection

| Setting | Default | Description |
|---------|---------|-------------|
| `sentinel_enabled` | `False` | Sampled Half-Space-Tree scoring |
| `sentinel_sample_rate` | `0.01` | Fraction of requests scored |
| `sentinel_block` | `False` | Deny (429) on anomaly instead of only logging |

### Defense Randomization

| Setting | Default | Description |
|---------|---------|-------------|
| `randomizer_enabled` | `False` | Per-session limit jitter |
| `randomizer_session_header` | `x-session-id` | Header carrying the session id |

### Honeypots

| Setting | Default | Description |
|---------|---------|-------------|
| `honeypot_paths` | `[]` | Trap paths (exact match); hits get 404 |
| `honeypot_ban` | `True` | Record a ban violation on trap hits |

### Observability

| Setting | Default | Description |
|---------|---------|-------------|
| `metrics_enabled` | `False` | Enable Prometheus metrics |
| `logging_enabled` | `True` | Enable structured logging |
| `log_level` | `warning` | Logging level |
