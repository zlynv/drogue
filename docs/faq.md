# FAQ

## Why no `request: Request` in function signatures?

Most rate limiters require passing the request object through the signature. drogue extracts client identity from the framework's context directly. Your function signatures stay clean.

## Can I use it with existing middleware?

Yes. drogue works alongside existing middleware. Place it after authentication middleware if you want to rate-limit by user, or before if you want to rate-limit by IP.

## What if Redis goes down?

drogue fails closed by default. If the storage backend is unreachable, requests are denied. You can configure `fail_open=True` to allow requests through.

## How do I migrate from slowapi?

See [Migration from slowapi](migration/slowapi.md). The key changes: remove `request: Request` from signatures, replace `@limiter.limit` with drogue's decorator.

## Does it support WebSocket rate limiting?

Yes. FastAPI adapters support WebSocket rate limiting via `@limiter.limit_ws()`.

## How does trust caching improve performance?

Trust state is cached in-memory per process. This avoids Redis round-trips for trusted clients, achieving 9x throughput improvement.

## What is shadow mode?

Shadow mode tests new rate limit rules without enforcing them. Requests are processed normally, but metrics are collected to show what would have been limited. Use this to tune limits before enforcement.

## How do I configure for production?

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    redis_url="redis://localhost:6379",
    ddos_enabled=True,
    ban_enabled=True,
)
```

## Does it work with gRPC?

drogue currently supports HTTP frameworks (FastAPI, Django, Flask). gRPC support is planned for v0.3.

## Can I use custom algorithms?

Yes. Implement the `Algorithm` abstract base class and register it.
