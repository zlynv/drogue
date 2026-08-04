# Migrating from slowapi

## Overview

drogue provides rate limiting and DDoS protection for FastAPI with additional features like WebSocket support, trust caching, and a protection pipeline. If you're migrating from slowapi, the API is similar but not identical.

## Before (slowapi)

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data(request: Request):  # polluted signature
    return {"data": "value"}
```

## After (drogue)

```python
from drogue.adapters.fastapi import DrogueLimiter

limiter = DrogueLimiter(app)

@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data():  # clean signature
    return {"data": "value"}
```

## Migration Checklist

1. **Replace imports:**

```python
# Before
from slowapi import Limiter
from slowapi.util import get_remote_address

# After
from drogue.adapters.fastapi import DrogueLimiter
```

2. **Replace limiter initialization:**

```python
# Before
limiter = Limiter(key_func=get_remote_address)

# After
limiter = DrogueLimiter(app)
```

3. **Remove `request: Request` from decorated endpoints:**

```python
# Before
@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data(request: Request):
    return {"data": "value"}

# After
@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data():
    return {"data": "value"}
```

4. **Rate limit headers work the same:**

Both libraries inject the same headers:

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`
- `Retry-After`

5. **Redis configuration:**

```python
# Before (slowapi)
from slowapi.backends.redis import RedisBackend
limiter = Limiter(key_func=get_remote_address, backend=RedisBackend("redis://localhost:6379"))

# After (drogue)
from drogue.core.storage.redis import RedisStorage
storage = RedisStorage(url="redis://localhost:6379")
limiter = DrogueLimiter(app, storage=storage)
```

## Key Differences

| Aspect | slowapi | drogue |
|--------|---------|--------|
| Request parameter | Required | Not needed |
| WebSocket | Not supported | Supported |
| DDoS detection | Not available | Z-score + streaming |
| Trust caching | Not available | 9x throughput |
| Algorithms | Token Bucket | Token Bucket, Sliding Window, Fixed Window, GCRA, Leaky Bucket |
| Storage | Redis, Memcached | Memory, Redis, Count-Min Sketch |

## Additional Features

Once migrated, you gain access to:

- **DDoS detection** -- Enable with `ddos_enabled=True`
- **Trust caching** -- Automatic, no configuration needed
- **Probe detection** -- Enable with probe detector
- **Defense randomization** -- Enable with randomizer
- **Shadow mode** -- Test rules without enforcing
- **CIDR filtering** -- Block/allow IP ranges
- **Adaptive limits** -- System-aware throttling

## Rollback

If you need to rollback to slowapi:

1. Revert imports
2. Revert limiter initialization
3. Add `request: Request` back to endpoints
4. Revert Redis configuration
