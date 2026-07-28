# Django Getting Started

## Installation

```bash
pip install drogue[django]
```

## Basic Usage

```python
# settings.py
from drogue.adapters.django import DrogueRateLimiter

DROGUE_LIMITER = DrogueRateLimiter(default_limits=["100/minute"])

MIDDLEWARE = [
    # ... existing middleware
    "drogue.adapters.django.DrogueMiddleware",
]
```

```python
# views.py
from django.http import JsonResponse
from drogue.adapters.django import DrogueRateLimiter

limiter = DROGUE_LIMITER

@limiter.limit("10/minute")
def get_data(request):
    return JsonResponse({"data": "value"})
```

## Configuration

```python
# settings.py
from drogue.adapters.django import DrogueRateLimiter
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    default_algorithm="token_bucket",
    ban_enabled=True,
    ddos_enabled=True,
)

DROGUE_LIMITER = DrogueRateLimiter(
    config=config,
    default_limits=["100/minute"],
)

MIDDLEWARE = [
    # ... existing middleware
    "drogue.adapters.django.DrogueMiddleware",
]
```

## Per-View Limits

```python
from django.http import JsonResponse
from drogue.adapters.django import DrogueRateLimiter

limiter = DROGUE_LIMITER

@limiter.limit("100/minute")
def public_view(request):
    return JsonResponse({"data": "public"})

@limiter.limit("10/minute")
def private_view(request):
    return JsonResponse({"data": "private"})
```

## Middleware for Global Limits

The `DrogueMiddleware` applies global rate limits to all views:

```python
MIDDLEWARE = [
    # ... existing middleware
    "drogue.adapters.django.DrogueMiddleware",
]
```

## Redis Backend

```python
# settings.py
from drogue.core.storage.redis import RedisStorage

storage = RedisStorage(url="redis://localhost:6379")

DROGUE_LIMITER = DrogueRateLimiter(
    storage=storage,
    default_limits=["100/minute"],
)
```

## Async Views

```python
from django.http import JsonResponse
from drogue.adapters.django import DrogueRateLimiter

limiter = DROGUE_LIMITER

@limiter.limit("10/minute")
async def async_view(request):
    return JsonResponse({"data": "async"})
```
