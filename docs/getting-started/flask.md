# Flask Getting Started

## Installation

```bash
pip install drogue
```

## Basic Usage

```python
from flask import Flask, jsonify
from drogue.adapters.flask import DrogueLimiter

app = Flask(__name__)
limiter = DrogueLimiter(app, default_limits=["100/minute"])

@app.route("/api/data")
@limiter.limit("10/minute")
def get_data():
    return jsonify({"data": "value"})
```

## Configuration

```python
from flask import Flask, jsonify
from drogue.adapters.flask import DrogueLimiter
from drogue.core.config import DrogueConfig

app = Flask(__name__)

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

@app.route("/api/data")
@limiter.limit("10/minute")
def get_data():
    return jsonify({"data": "value"})
```

## Global Rate Limiting

The `before_request` hook applies global rate limits to all routes:

```python
limiter = DrogueLimiter(
    app,
    default_limits=["100/minute"],  # Applied to all routes
)
```

## Per-Route Limits

```python
@app.route("/api/public")
@limiter.limit("100/minute")
def public_endpoint():
    return jsonify({"data": "public"})

@app.route("/api/private")
@limiter.limit("10/minute")
def private_endpoint():
    return jsonify({"data": "private"})
```

## Redis Backend

```python
from drogue.core.storage.redis import RedisStorage

storage = RedisStorage(url="redis://localhost:6379")
limiter = DrogueLimiter(app, storage=storage)
```
