# Logging

## Setup

```python
from drogue.observability.logging import StructuredRateLimitLogger

logger = StructuredRateLimitLogger(
    level="INFO",
    json_format=True,
    include_client_ip=True,
    include_request_path=True,
    include_rate_limit_info=True,
)
```

## Log events

| Event | Level | When |
|-------|-------|------|
| `request_allowed` | DEBUG | Request passes rate limit |
| `request_limited` | WARNING | Request is rate limited |
| `ban_issued` | WARNING | Client is banned |
| `ddos_detected` | WARNING | Anomaly detected |
| `trust_transition` | INFO | Trust state changes |
| `circuit_breaker_trip` | WARNING | Circuit opens |

## Log format

```json
{
    "timestamp": "2026-07-28T22:30:00.000Z",
    "level": "warning",
    "event": "request_limited",
    "client_ip": "192.168.1.1",
    "request_path": "/api/data",
    "rate_limit": "10/minute",
    "remaining": 0,
    "algorithm": "token_bucket",
    "key": "192.168.1.1"
}
```

## Integration

```python
from drogue.observability.logging import StructuredRateLimitLogger
from drogue.core.config import DrogueConfig

logger = StructuredRateLimitLogger(level="INFO")
config = DrogueConfig(log_level="info")
```
