"""FastAPI example with drogue rate limiting."""

from fastapi import Depends, FastAPI

from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.config import DrogueConfig

app = FastAPI(title="Drogue FastAPI Example")

# Configure with protection layer
config = DrogueConfig(
    ban_enabled=True,
    ban_threshold=5,
    ddos_enabled=True,
    circuit_breaker_enabled=True,
)

limiter = DrogueLimiter(
    app,
    config=config,
    default_limits=["100/minute"],
)


@app.get("/")
@limiter.limit("10/minute")
async def root():
    return {"message": "Hello, World!"}


@app.get("/expensive")
@limiter.limit("3/minute")
async def expensive_endpoint():
    """Simulate an expensive operation."""
    return {"result": "computed"}


@app.get("/dep")
async def dependency_route(_=Depends(limiter.dependency("5/minute"))):
    return {"ok": True}
