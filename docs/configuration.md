# Configuration

drogue is configured through a `DrogueConfig` dataclass. All options have sensible defaults.

## Usage

```python
from drogue.core.config import DrogueConfig
from drogue.adapters.fastapi import DrogueLimiter

config = DrogueConfig(
    default_algorithm="token_bucket",
    ban_enabled=True,
    ddos_enabled=True,
)

limiter = DrogueLimiter(app, config=config)
```

## General

| Option | Default | Description |
|--------|---------|-------------|
| `default_algorithm` | `"token_bucket"` | Default algorithm. Options: `"token_bucket"`, `"sliding_window"`, `"fixed_window"` |
| `default_fail_closed` | `True` | If `True`, deny requests when the storage backend is unavailable |
| `default_headers` | `True` | Inject `X-RateLimit-*` headers in responses |
| `default_retry_after` | `True` | Include `Retry-After` header when rate limited |

## Proxy handling

| Option | Default | Description |
|--------|---------|-------------|
| `trusted_proxies` | `[]` | List of trusted proxy CIDRs for `X-Forwarded-For` parsing |
| `proxy_header` | `"x-forwarded-for"` | Header to read client IP from |
| `trust_x_real_ip` | `True` | Trust the `X-Real-IP` header |

```python
config = DrogueConfig(
    trusted_proxies=["10.0.0.0/8", "172.16.0.0/12"],
    trust_x_real_ip=True,
)
```

## Progressive auto-ban

| Option | Default | Description |
|--------|---------|-------------|
| `ban_enabled` | `False` | Enable progressive auto-ban |
| `ban_threshold` | `5` | Number of violations before ban triggers |
| `ban_window` | `300.0` | Time window to count violations (seconds) |
| `ban_escalation` | `[0, 60, 600, 3600, 86400]` | Ban durations per escalation level |

The escalation list defines ban durations in seconds. Default: warning (0s), 1 minute, 10 minutes, 1 hour, 24 hours.

```python
config = DrogueConfig(
    ban_enabled=True,
    ban_threshold=3,
    ban_escalation=[0, 60, 3600, 86400],
)
```

## DDoS detection

| Option | Default | Description |
|--------|---------|-------------|
| `ddos_enabled` | `False` | Enable Z-score DDoS detection |
| `ddos_z_score_threshold` | `3.0` | Z-score threshold for anomaly detection |
| `ddos_min_samples` | `100` | Minimum request samples before detection activates |
| `ddos_window` | `60.0` | Sliding window for rate calculation (seconds) |

```python
config = DrogueConfig(
    ddos_enabled=True,
    ddos_z_score_threshold=2.5,
    ddos_min_samples=50,
)
```

## Circuit breaker

| Option | Default | Description |
|--------|---------|-------------|
| `circuit_breaker_enabled` | `False` | Enable circuit breaker |
| `circuit_failure_threshold` | `5` | Failures before circuit opens |
| `circuit_recovery_timeout` | `30.0` | Seconds before half-open test |
| `circuit_jitter` | `0.2` | Random jitter on recovery timeout (0-1) |

```python
config = DrogueConfig(
    circuit_breaker_enabled=True,
    circuit_failure_threshold=3,
    circuit_recovery_timeout=60.0,
)
```

## Storage

| Option | Default | Description |
|--------|---------|-------------|
| `storage_backend` | `"memory"` | Backend type: `"memory"` or `"redis"` |
| `redis_url` | `"redis://localhost:6379"` | Redis connection URL |

```python
config = DrogueConfig(
    storage_backend="redis",
    redis_url="redis://myhost:6379/0",
)
```

## Shadow mode

| Option | Default | Description |
|--------|---------|-------------|
| `shadow_enabled` | `False` | Evaluate rules but allow all requests (for testing) |

## CIDR filtering

| Option | Default | Description |
|--------|---------|-------------|
| `cidr_allowlist` | `[]` | CIDR ranges to allow (empty = allow all) |
| `cidr_denylist` | `[]` | CIDR ranges to deny |

## Adaptive rate limiting

| Option | Default | Description |
|--------|---------|-------------|
| `adaptive_enabled` | `False` | Enable system-metric-based adaptive limits |
| `adaptive_cpu_threshold` | `0.8` | CPU usage above which limits are reduced |
| `adaptive_memory_threshold` | `0.8` | Memory usage above which limits are reduced |
| `adaptive_latency_threshold` | `1.0` | p95 latency (seconds) above which limits are reduced |
| `adaptive_check_interval` | `5.0` | How often to check system metrics (seconds) |

Requires the `adaptive` extra: `pip install drogue[adaptive]`

## Observability

| Option | Default | Description |
|--------|---------|-------------|
| `metrics_enabled` | `False` | Enable metrics collection |
| `logging_enabled` | `True` | Enable structured logging |
| `log_level` | `"warning"` | Log level for drogue events |
