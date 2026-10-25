# AGENTS.md

drogue is a rate limiting and application-layer protection library for Python. It supports FastAPI, Flask, Django, and Django REST Framework.

## Core selling point

**No `request: Request` in your function signatures.** drogue extracts identity
(IP, user, header) from the ASGI/WSGI context without polluting endpoint signatures.
This is the primary differentiator from slowapi and similar libraries.

## Quick start

### FastAPI

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter

app = FastAPI()
limiter = DrogueLimiter(app, default_limits=["100/minute"])

@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data():
    return {"data": "value"}   # no request parameter needed
```

Sync endpoints are supported (the decorator handles both `def` and `async def`).

### Flask

```python
from flask import Flask
from drogue.adapters.flask import DrogueLimiter

app = Flask(__name__)
limiter = DrogueLimiter(app, default_limits=["100/minute"])

@app.route("/api/data")
@limiter.limit("10/minute")
def get_data():
    return {"data": "value"}
```

### Django

```python
# settings.py
MIDDLEWARE = [
    "drogue.adapters.django.DrogueMiddleware",
]

# views.py
from drogue.adapters.django import DrogueRateLimiter
limiter = DrogueRateLimiter()

@limiter.limit("10/minute")
def get_data(request):
    return JsonResponse({"data": "value"})
```

### DRF throttle

```python
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": ["drogue.adapters.django.throttle.DrogueThrottle"],
}
```

## Rate limit strings

```python
"100/minute"           # 100 requests per minute
"10/second;50/minute"  # multiple windows (parse_rule_string)
"100/minute@cost=2"    # cost-aware (not yet parsed by default)
```

Algorithms: `AlgorithmType.TOKEN_BUCKET` (default), `SLIDING_WINDOW`, `FIXED_WINDOW`, `GCRA`, `LEAKY_BUCKET`.

Token Bucket permits short bursts above the average rate. For strict per-window quotas use `algorithm=AlgorithmType.FIXED_WINDOW`.

## Identity extractors

- `RemoteAddressExtractor` (default) - client IP, anti-spoof X-Forwarded-For
- `UserExtractor` - user ID from request context
- `HeaderExtractor` - custom header value
- `CompositeExtractor` - combine multiple

## Storage

- `MemoryStorage` (default, in-process)
- `RedisStorage(url="redis://localhost")` (multi-process)
- `MongoDBStorage(...)` (via Motor)

## Configuration (DrogueConfig)

All defenses are **off by default**. Enable what you need.

| Field | Default | Purpose |
|-------|---------|---------|
| `default_fail_closed` | `True` | Deny (429) on backend failure vs allow |
| `shadow_enabled` | `False` | Log-only mode |
| `cidr_allowlist` / `cidr_denylist` | `[]` | IP filtering |
| `ban_enabled` / `ddos_enabled` / `circuit_breaker_enabled` | `False` | Protection layers |
| `trust_enabled` | `False` | Trust fast-path |
| `challenge_enabled` | `False` | CAPTCHA interstitials |

## 429 response customization

Use `error_renderer` to build your own 429 body:

```python
from starlette.responses import JSONResponse

def my_renderer(request, exc, headers):
    return JSONResponse({"error": "slow_down"}, status_code=429, headers=headers)

limiter = DrogueLimiter(app, error_renderer=my_renderer)
```

Headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`)
are injected automatically on all responses when `rule.headers=True` (default).

## Migration from slowapi

- Remove `request: Request` from decorated endpoints
- Replace `Limiter(key_func=...)` with `DrogueLimiter(app)`
- drogue defaults to Token Bucket (burst-friendly); slowapi uses Fixed Window (strict)
- `error_renderer` replaces custom exception handlers for 429 bodies

## What drogue does NOT do

SQL injection, XSS, CSRF, authentication, authorization. Use a dedicated security stack.
