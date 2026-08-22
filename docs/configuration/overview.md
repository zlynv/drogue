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

    # Observability
    metrics_enabled=True,
    logging_enabled=True,
    log_level="warning",
)
```

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

### Observability

| Setting | Default | Description |
|---------|---------|-------------|
| `metrics_enabled` | `False` | Enable Prometheus metrics |
| `logging_enabled` | `True` | Enable structured logging |
| `log_level` | `warning` | Logging level |
