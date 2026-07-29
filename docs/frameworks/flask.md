---
description: Rate limiting for Flask with drogue. Decorator-based limits with Redis backend support.
---

# Flask

## Setup

```bash
pip install drogue[flask]
```

```python
from flask import Flask
from drogue.adapters.flask import DrogueLimiter

app = Flask(__name__)
limiter = DrogueLimiter(app, default_limits=["100/minute"])
```

## Decorator

```python
@app.route("/api/data")
@limiter.limit("10/minute")
def get_data():
    return {"data": "value"}
```

## Global limits

```python
limiter = DrogueLimiter(app, default_limits=["100/minute"])
```

## Multiple rules

```python
@app.route("/api/data")
@limiter.limit("10/minute")
@limiter.limit("100/hour")
def get_data(): ...
```

## Custom key function

```python
from drogue.core.identity import UserExtractor

limiter = DrogueLimiter(app, key_func=UserExtractor())

@app.route("/api/data")
@limiter.limit("10/minute")
def get_data(): ...
```

## Algorithm selection

```python
from drogue.core.rules.rule import AlgorithmType

@app.route("/api/data")
@limiter.limit("10/minute", algorithm=AlgorithmType.SLIDING_WINDOW)
def get_data(): ...
```

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(ban_enabled=True, ddos_enabled=True)
limiter = DrogueLimiter(app, config=config)
```
