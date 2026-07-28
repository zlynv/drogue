# Rate Limiting

## Overview

drogue provides three rate limiting algorithms with a unified API.

## Basic Usage

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter

app = FastAPI()
limiter = DrogueLimiter(app, default_limits=["100/minute"])

@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data():
    return {"data": "value"}
```

## Cost-Aware Limits

Expensive operations can consume more tokens:

```python
@app.post("/api/heavy")
@limiter.limit("10/minute")
async def heavy_operation():
    # Cost is determined by the route's rule
    return {"result": "computed"}
```

## Blocking Mode

Wait until tokens are available instead of rejecting:

```python
@app.get("/api/data")
@limiter.limit("10/minute", block=True, timeout=5.0)
async def get_data():
    return {"data": "value"}
```

## Rate Limit Headers

drogue automatically injects standard rate limit headers:

- `X-RateLimit-Limit` -- Maximum requests allowed
- `X-RateLimit-Remaining` -- Requests remaining
- `X-RateLimit-Reset` -- Time until limit resets
- `Retry-After` -- Seconds until retry (on 429)

## 429 Response

When rate limited, drogue returns a 429 response:

```json
{
  "error": "Rate limit exceeded",
  "retry_after": 30,
  "limit": 10,
  "remaining": 0
}
```

## WebSocket Rate Limiting

```python
@app.websocket("/ws")
@limiter.limit_ws("100/minute")
async def websocket_endpoint(websocket):
    await websocket.accept()
    # ...
```

## Dependency Injection

```python
from fastapi import Depends

@app.get("/api/data")
async def get_data(rate_limit=Depends(limiter.dependency("10/minute"))):
    return {"data": "value"}
```

## Custom Key Functions

```python
from drogue.core.identity import UserExtractor

@app.get("/api/data")
@limiter.limit("10/minute", key_func=UserExtractor())
async def get_data():
    return {"data": "value"}
```
