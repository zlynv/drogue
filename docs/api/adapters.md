# Adapters API Reference

## FastAPI

### DrogueLimiter

```python
from drogue.adapters.fastapi import DrogueLimiter

limiter = DrogueLimiter(
    app=None,                    # FastAPI app (optional, can use init_app)
    rules=None,                  # Default rules list
    storage=None,                # Storage backend (default: MemoryStorage)
    key_func=None,               # Identity extractor (default: RemoteAddressExtractor)
    config=None,                 # DrogueConfig
    default_limits=None,         # Default rate limit strings
)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `init_app(app)` | Initialize with FastAPI app |
| `limit(rule_str, *, algorithm, block, timeout, key_func)` | Decorator for rate limiting |
| `dependency(rule_str, *, algorithm, key_func)` | FastAPI dependency factory |
| `limit_ws(rule_str, *, algorithm, key_func)` | WebSocket rate limiting |
| `get_shadow_stats()` | Get shadow mode statistics |
| `clear_shadow_stats()` | Clear shadow statistics |
| `get_cidr_filter()` | Get CIDR filter instance |
| `get_adaptive_metrics()` | Get adaptive rate limiting metrics |

**Usage:**

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter

app = FastAPI()
limiter = DrogueLimiter(app)

@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data():
    return {"data": "value"}
```

**Advanced Usage:**

```python
from drogue.core.config import DrogueConfig
from drogue.core.storage.redis import RedisStorage

config = DrogueConfig(ddos_enabled=True, ban_enabled=True)
storage = RedisStorage(url="redis://localhost:6379")
limiter = DrogueLimiter(app, config=config, storage=storage)

@app.websocket("/ws")
@limiter.limit_ws("10/second")
async def websocket_endpoint(websocket):
    await websocket.accept()
    # ...
```

---

## Django

### DrogueRateLimiter

```python
from drogue.adapters.django import DrogueRateLimiter

limiter = DrogueRateLimiter(
    rules=None,                  # Default rules list
    storage=None,                # Storage backend
    key_func=None,               # Identity extractor
    config=None,                 # DrogueConfig
    default_limits=None,         # Default rate limit strings
)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `initialize()` | Initialize the limiter |
| `limit(rule_str, *, algorithm, block, key_func)` | Decorator for rate limiting |
| `_check(key, rule, context, route_key)` | Async rate limit check |
| `_check_sync(key, rule, context, route_key)` | Sync rate limit check |

### DrogueMiddleware

```python
from drogue.adapters.django import DrogueMiddleware
```

**Usage:**

```python
# settings.py
MIDDLEWARE = [
    "drogue.adapters.django.DrogueMiddleware",
    # ...
]

DROGUE_CONFIG = {
    "ban_enabled": True,
    "ddos_enabled": True,
}
```

**Key:**

- Import from `drogue.adapters.django` (not `drogue.adapters.django.limiter`)
- `DrogueMiddleware` is Django middleware that processes requests
- `DrogueRateLimiter` is used in views with `@limiter.limit()` decorator

---

## Flask

### DrogueLimiter

```python
from drogue.adapters.flask import DrogueLimiter

limiter = DrogueLimiter(
    app=None,                    # Flask app (optional, can use init_app)
    rules=None,                  # Default rules list
    storage=None,                # Storage backend
    key_func=None,               # Identity extractor
    config=None,                 # DrogueConfig
    default_limits=None,         # Default rate limit strings
)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `init_app(app)` | Initialize with Flask app |
| `limit(rule_str, *, algorithm, block, key_func)` | Decorator for rate limiting |
| `_check(key, rule, context, route_key)` | Async rate limit check |
| `_check_sync(key, rule, context, route_key)` | Sync rate limit check |

**Usage:**

```python
from flask import Flask
from drogue.adapters.flask import DrogueLimiter

app = Flask(__name__)
limiter = DrogueLimiter(app)

@app.route("/api/data")
@limiter.limit("10/minute")
def get_data():
    return {"data": "value"}
```

---

## Common Parameters

### Rate Limit Strings

```python
"100/minute"           # 100 requests per minute
"10/second"            # 10 requests per second
"1000/hour"            # 1000 requests per hour
"10/second;50/minute"  # Burst: 10/s, sustained: 50/min
```

### Algorithm Types

```python
from drogue.core.rules.rule import AlgorithmType

AlgorithmType.TOKEN_BUCKET      # Burst-friendly, leaky bucket
AlgorithmType.SLIDING_WINDOW    # Precise, no boundary burst
AlgorithmType.FIXED_WINDOW      # Simplest, lowest memory
```

### Block vs Throttle

```python
# Block mode: return 429 immediately
@limiter.limit("10/minute", block=True)

# Throttle mode: wait for slot (default)
@limiter.limit("10/minute", block=False)
```

### Custom Key Functions

```python
from drogue.core.identity import RemoteAddressExtractor, UserExtractor, HeaderExtractor

# By IP (default)
limiter = DrogueLimiter(app, key_func=RemoteAddressExtractor())

# By user ID
limiter = DrogueLimiter(app, key_func=UserExtractor())

# By API key header
limiter = DrogueLimiter(app, key_func=HeaderExtractor(header_name="X-API-Key"))
```
