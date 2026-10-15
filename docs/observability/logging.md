# Logging

## Setup

```python
import logging
from drogue.observability.logging import StructuredRateLimitLogger

logger = StructuredRateLimitLogger(
    logger_name="drogue",
    level=logging.INFO,
)
```

## Log events

| Method | `event` value | Fields |
|--------|---------------|--------|
| `log_allowed(key, route, remaining, limit, latency_ms=None)` | `rate_limit_allowed` | `key, route, remaining, limit, latency_ms` |
| `log_rejected(key, route, retry_after, limit, remaining=0)` | `rate_limit_rejected` | `key, route, retry_after, limit, remaining` |
| `log_ban(key, level, expires_in=None, reason="rate_limit_violations")` | `ban_issued` | `key, level, expires_in, reason` |
| `log_ban_expired(key, level)` | `ban_expired` | `key, level` |
| `log_ddos(key, z_score, global_rate, client_rate)` | `ddos_detected` | `key, z_score, global_rate, client_rate` |
| `log_circuit_break(state, failure_count=0, success_count=0)` | `circuit_breaker` | `state, failure_count, success_count` |
| `log_error(message, error=None, **kwargs)` | `error` | `message, error_type, error_message` |

## Log format

Each record is one JSON line written at the configured stdlib level:

```json
{"timestamp": 1785670200.0, "event": "rate_limit_rejected", "key": "192.168.1.1", "route": "/api/data", "retry_after": 30, "limit": 10, "remaining": 0}
```

`timestamp` is epoch seconds (not ISO 8601). The stdlib log level lives
on the `LogRecord`, not inside the JSON payload.

## Integration

```python
from drogue.observability.logging import StructuredRateLimitLogger
from drogue.core.config import DrogueConfig

logger = StructuredRateLimitLogger()
config = DrogueConfig(log_level="warning")
```

Call the `log_*` methods yourself around limiter decisions; adapters do
not emit these automatically (except FastAPI shadow-mode notices).
