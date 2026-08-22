# FastAPI Getting Started

## Installation

```bash
pip install drogue[fastapi]
```

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

## Dependency Injection

```python
from fastapi import FastAPI, Depends
from drogue.adapters.fastapi import DrogueLimiter

app = FastAPI()
limiter = DrogueLimiter(app)

@app.get("/api/data")
async def get_data(rate_limit=Depends(limiter.dependency("10/minute"))):
    return {"data": "value"}
```

## WebSocket Rate Limiting

```python
from fastapi import FastAPI, WebSocket
from drogue.adapters.fastapi import DrogueLimiter

app = FastAPI()
limiter = DrogueLimiter(app)

@app.websocket("/ws")
@limiter.limit_ws("100/minute")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Handle WebSocket connection
```

## Configuration

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.config import DrogueConfig

app = FastAPI()

config = DrogueConfig(
    default_algorithm="token_bucket",
    ban_enabled=True,
    ddos_enabled=True,
)

limiter = DrogueLimiter(
    app,
    config=config,
    default_limits=["100/minute"],
)
```

## Behind a Reverse Proxy (nginx, Traefik, Cloudflare)

When running behind a proxy, **you must configure `trusted_proxies`** to correctly identify clients. Without it, forwarded headers are ignored and all requests appear to come from the proxy itself.

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.config import DrogueConfig

app = FastAPI()

config = DrogueConfig(
    trusted_proxies=["10.0.0.0/8", "172.16.0.0/12"],  # your proxy CIDR ranges
    proxy_header="x-forwarded-for",
    trust_x_real_ip=True,
)

limiter = DrogueLimiter(app, config=config)
```

**Security note:** Without `trusted_proxies` configured, `X-Forwarded-For` and `X-Real-IP` headers are **completely ignored**. Clients cannot spoof their identity by sending these headers directly to your application.

## Shadow Mode

Test rules without enforcing:

```python
@app.get("/api/data")
@limiter.limit("10/minute", shadow=True)
async def get_data():
    return {"data": "value"}

# Check what would have been blocked
stats = limiter.get_shadow_stats()
```
