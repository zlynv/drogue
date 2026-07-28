# Django

## Setup

```bash
pip install drogue[django]
```

### Middleware (global limits)

**settings.py:**

```python
MIDDLEWARE = [
    "drogue.adapters.django.DrogueMiddleware",
]
```

### View decorator

```python
from drogue.adapters.django import DrogueRateLimiter
from django.http import JsonResponse

limiter = DrogueRateLimiter()

@limiter.limit("10/minute")
def get_data(request):
    return JsonResponse({"data": "value"})
```

## Configuration

**settings.py:**

```python
DROGUE_CONFIG = {
    "ban_enabled": True,
    "ddos_enabled": True,
    "trusted_proxies": ["10.0.0.0/8"],
}
```

## Multiple rules

```python
@limiter.limit("10/minute")
@limiter.limit("100/hour")
def get_data(request): ...
```

## Custom key function

```python
from drogue.core.identity import UserExtractor

limiter = DrogueRateLimiter(key_func=UserExtractor())

@limiter.limit("10/minute")
def get_data(request): ...
```

## Django REST Framework

```python
from drogue.adapters.django.throttle import DrogueThrottle
from rest_framework.views import APIView

class MyView(APIView):
    throttle_classes = [DrogueThrottle]

    def get(self, request):
        return Response({"data": "value"})
```

## Rate limit headers

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests allowed |
| `X-RateLimit-Remaining` | Requests remaining |
| `X-RateLimit-Reset` | Unix timestamp when window resets |
| `Retry-After` | Seconds until next request (only on 429) |
