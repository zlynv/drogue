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
