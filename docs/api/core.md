# Core API Reference

## DrogueConfig

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

## RateLimitRule

```python
from drogue.core.rules.rule import RateLimitRule, parse_rule_string

# Parse from string
rule = parse_rule_string("100/minute")

# Create directly
rule = RateLimitRule(
    limit=100,
    window=60.0,
    algorithm=AlgorithmType.TOKEN_BUCKET,
    block=False,
    timeout=None,
    shadow=False,
)
```

## AlgorithmType

```python
from drogue.core.rules.rule import AlgorithmType

AlgorithmType.TOKEN_BUCKET
AlgorithmType.SLIDING_WINDOW
AlgorithmType.FIXED_WINDOW
AlgorithmType.GCRA
AlgorithmType.LEAKY_BUCKET
```

## AcquireResult

```python
from drogue.core.abstracts import AcquireResult

result = AcquireResult(
    allowed=True,
    limit=100,
    remaining=99,
    retry_after=0,
    reset_at=1690000060.0,
)

# Headers are auto-generated from fields
result.headers
# {"X-RateLimit-Limit": "100", "X-RateLimit-Remaining": "99", "X-RateLimit-Reset": "1690000060"}
```

## Exceptions

```python
from drogue.core.errors import (
    DrogueError,           # Base exception
    RateLimitExceeded,     # Rate limit exceeded (429)
    BackendFailure,        # Storage backend failure
    BanError,              # Client is banned
    ConfigurationError,    # Invalid configuration
    StorageError,          # Storage operation failure
)
```

## Storage

```python
from drogue.core.storage.memory import MemoryStorage
from drogue.core.storage.redis import RedisStorage

memory = MemoryStorage()
redis = RedisStorage(url="redis://localhost:6379")
```

## Identity Extractors

```python
from drogue.core.identity import (
    RemoteAddressExtractor,
    UserExtractor,
    HeaderExtractor,
    PathExtractor,
    StaticKeyExtractor,
    CompositeExtractor,
)

# IP-based
extractor = RemoteAddressExtractor(
    trusted_proxies=["10.0.0.0/8"],
    trust_x_real_ip=True,
)

# User-based
extractor = UserExtractor()

# Header-based
extractor = HeaderExtractor(header_name="X-API-Key")

# Path-based
extractor = PathExtractor()

# Static key
extractor = StaticKeyExtractor(key="global")

# Composite
extractor = CompositeExtractor(
    extractors=[RemoteAddressExtractor(), UserExtractor()]
)
```
