"""FastAPI example with Redis backend for distributed rate limiting."""

from fastapi import Depends, FastAPI

from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.config import DrogueConfig
from drogue.core.storage.redis import RedisStorage

app = FastAPI(title="Drogue Redis Example")

# Redis backend for distributed rate limiting
storage = RedisStorage(url="redis://localhost:6379")

config = DrogueConfig(
    ban_enabled=True,
    ban_threshold=5,
    ddos_enabled=True,
    circuit_breaker_enabled=True,
    metrics_enabled=True,
    storage_backend="redis",
    redis_url="redis://localhost:6379",
)

limiter = DrogueLimiter(
    app,
    config=config,
    storage=storage,
    default_limits=["100/minute"],
)


@app.get("/")
@limiter.limit("10/minute")
async def root():
    return {"message": "Hello, Redis!"}


@app.get("/expensive")
@limiter.limit("3/minute")
async def expensive_endpoint():
    """Simulate an expensive operation."""
    return {"result": "computed"}


@app.get("/dep")
async def dependency_route(_=Depends(limiter.dependency("5/minute"))):
    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics."""
    from drogue.observability.metrics import get_metrics
    return get_metrics()
