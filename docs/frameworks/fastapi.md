# FastAPI

## Setup

```bash
pip install drogue[fastapi]
```

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter

app = FastAPI()
limiter = DrogueLimiter(app, default_limits=["100/minute"])
```

## Decorator

```python
@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data():
    return {"data": "value"}
```

No `request: Request` parameter needed.

## Dependency injection

```python
from fastapi import Depends

@app.get("/api/data")
async def get_data(rate_limit=Depends(limiter.dependency("10/minute"))):
    return {"data": "value"}
```

## WebSocket rate limiting

```python
@app.websocket("/ws")
@limiter.limit_ws("100/minute")
async def websocket_endpoint(websocket):
    await websocket.accept()
```

## Custom key function

```python
from drogue.core.identity import UserExtractor

@app.get("/api/data")
@limiter.limit("10/minute", key_func=UserExtractor())
async def get_data(): ...
```

## Algorithm selection

```python
from drogue.core.rules.rule import AlgorithmType

@app.get("/api/data")
@limiter.limit("10/minute", algorithm=AlgorithmType.SLIDING_WINDOW)
async def get_data(): ...
```

## Blocking mode

```python
@app.get("/api/data")
@limiter.limit("10/minute", block=True, timeout=5.0)
async def get_data(): ...
```

## Shadow mode

Test rules without enforcing:

```python
@app.get("/api/data")
@limiter.limit("10/minute", shadow=True)
async def get_data(): ...

stats = limiter.get_shadow_stats()
```

## Rate limit headers

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests allowed |
| `X-RateLimit-Remaining` | Requests remaining |
| `X-RateLimit-Reset` | Unix timestamp when window resets |
| `Retry-After` | Seconds until next request (only on 429) |
