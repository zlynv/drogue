# Why drogue exists (and why `request: Request` is wrong)

## The problem

Every Python rate limiter forces you to write this:

```python
@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data(request: Request):   # why?
    return {"data": "value"}
```

You just added a rate limit to one endpoint. Now your function signature
depends on the rate limiter. Change the limiter, rewrite every endpoint.
Test the endpoint without HTTP, mock the request. The rate limiter has
infected your business logic.

This is how slowapi works. It's how flask-limiter works. It's how
django-ratelimit works. They all require `request: Request` (or `request`)
in the function signature so the limiter can extract the client identity.

## The drogue approach

drogue extracts identity from the ASGI/WSGI context without polluting
endpoint signatures. The rate limiter is invisible to your code:

```python
@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data():
    return {"data": "value"}   # clean
```

No `request: Request`. No mock requests in tests. No coupling between
your business logic and the rate limiter.

## How it works

drogue sits in the ASGI middleware layer (or the WSGI hook for Flask/Django).
When a request arrives, the middleware extracts identity (IP, user ID, header)
before your endpoint runs. The decorator wraps the endpoint, checks the limit,
and either passes through or returns 429. Your function never sees the request.

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter

app = FastAPI()
limiter = DrogueLimiter(app, default_limits=["100/minute"])

@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data():
    return {"data": "value"}

@app.post("/api/upload")
@limiter.limit("5/minute")
async def upload(file: UploadFile):
    return {"filename": file.filename}
```

Both endpoints are rate limited. Neither has `request: Request` in its signature.

## Migration from slowapi

```python
# Before (slowapi)
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data(request: Request):
    return {"data": "value"}

# After (drogue)
from drogue.adapters.fastapi import DrogueLimiter

limiter = DrogueLimiter(app)

@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data():
    return {"data": "value"}
```

Three changes: import, initialization, remove `request: Request`. Done.

## What else drogue gives you

- **Token Bucket, Sliding Window, Fixed Window, GCRA, Leaky Bucket** (slowapi uses only Fixed Window)
- **WebSocket rate limiting** (slowapi has none)
- **DDoS detection** (Z-score anomaly detection)
- **Auto-ban** (progressive ban with doubling duration)
- **Trust scoring** (9x throughput for verified users)
- **CAPTCHA challenges** (Turnstile, signed pass cookies, replay-proof tokens)
- **Circuit breaker** (Closed/Open/HalfOpen states)
- **Shadow mode** (test rules without enforcing)
- **CIDR filtering** (allow/block IP ranges)
- **Custom 429 responses** (via `error_renderer` callback)

## Performance

drogue is fast. Token Bucket acquire runs in microseconds. Memory usage is
~150 bytes per key. The benchmarks live in the `benchmarks/` directory.

## When NOT to use drogue

drogue handles rate limiting and application-layer protection. It does NOT
solve SQL injection, XSS, CSRF, authentication, or authorization. Use a
dedicated security stack.

## Install

```bash
pip install drogue[fastapi]   # or [django], [flask], [drf]
```

[Full documentation](https://zlynv.github.io/drogue/) |
[Migration guide](../migration/slowapi.md) |
[GitHub](https://github.com/zlynv/drogue)
