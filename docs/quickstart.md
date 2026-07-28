# Quick Start

Get drogue running in under 5 minutes.

## FastAPI

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter

app = FastAPI()
limiter = DrogueLimiter(app, default_limits=["100/minute"])

@app.get("/api/data")
@limiter.limit("10/minute")
async def get_data():
    return {"data": "value"}

@app.get("/api/heavy")
@limiter.limit("3/minute")
async def heavy_operation():
    return {"result": "computed"}
```

Run it:

```bash
pip install drogue[fastapi]
uvicorn main:app
```

No `request` parameter. No middleware setup. Rate limit headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`) are injected automatically.

## Flask

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

```bash
pip install drogue[flask]
flask run
```

## Django

**settings.py:**

```python
MIDDLEWARE = [
    "drogue.adapters.django.DrogueMiddleware",
]
```

**views.py:**

```python
from drogue.adapters.django import DrogueRateLimiter
from django.http import JsonResponse

limiter = DrogueRateLimiter()

@limiter.limit("10/minute")
def get_data(request):
    return JsonResponse({"data": "value"})
```

```bash
pip install drogue[django]
python manage.py runserver
```

## Rate limit strings

| String | Meaning |
|--------|---------|
| `100/minute` | 100 requests per 60 seconds |
| `10/second` | 10 requests per 1 second |
| `1000/hour` | 1000 requests per 3600 seconds |

Combine burst and sustained:

```python
@limiter.limit("10/second;100/minute")
```

## Choosing an algorithm

```python
from drogue.core.rules.rule import AlgorithmType

@limiter.limit("100/minute", algorithm=AlgorithmType.TOKEN_BUCKET)      # default
@limiter.limit("100/minute", algorithm=AlgorithmType.SLIDING_WINDOW)   # most accurate
@limiter.limit("100/minute", algorithm=AlgorithmType.FIXED_WINDOW)     # simplest
```

## Next steps

- [Configuration](configuration.md) -- all available options
- [FastAPI guide](frameworks/fastapi.md) -- deep dive
- [Protection](protection/ddos.md) -- DDoS detection, auto-ban, trust caching
