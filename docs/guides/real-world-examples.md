# Real-World Examples

This page shows how to use drogue in common production scenarios.

---

## Login Rate Limiting

Prevent brute force attacks on your login endpoint.

### Strategy

- Per-IP limits for unauthenticated requests
- Per-user limits after authentication
- Progressive bans after repeated failures

### FastAPI Example

```python
from fastapi import FastAPI, Request
from drogue.adapters.fastapi import DrogueLimiter

app = FastAPI()
limiter = DrogueLimiter(app)

@app.post("/login")
@limiter.limit("5/minute")  # 5 attempts per minute per IP
async def login(request: Request):
    # ... authenticate user ...
    pass

@app.post("/login/verify")
@limiter.limit("10/minute")  # More generous after identity is known
async def login_verify(request: Request, user_id: str):
    # ... verify MFA code ...
    pass
```

### Django Example

```python
from drogue.adapters.django import DrogueRateLimiter
from django.http import JsonResponse

limiter = DrogueRateLimiter()

@limiter.limit("5/minute")
def login(request):
    # ... authenticate user ...
    pass
```

---

## API Key Rate Limiting

Enforce per-key quotas for API access.

### Strategy

- Extract API key from header
- Different limits per key or plan
- Cost-based limiting for expensive endpoints

### FastAPI Example

```python
from fastapi import FastAPI, Request
from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.identity import HeaderExtractor

app = FastAPI()
limiter = DrogueLimiter(
    app,
    key_func=HeaderExtractor("X-API-Key")  # Extract from API key header
)

@app.get("/api/data")
@limiter.limit("1000/day")  # 1000 requests per day per API key
async def get_data():
    return {"data": "value"}

@app.get("/api/heavy")
@limiter.limit("10/day", cost=10)  # Costs 10x against quota
async def heavy_computation():
    # ... expensive operation ...
    return {"result": "value"}
```

---

## WebSocket Rate Limiting

Protect WebSocket endpoints from abuse.

### Strategy

- Message rate limits per connection
- Connection limits per user
- DDoS protection for upgrade requests

### FastAPI Example

```python
from fastapi import FastAPI, WebSocket
from drogue.adapters.fastapi import DrogueLimiter

app = FastAPI()
limiter = DrogueLimiter(app)

@app.websocket("/ws/chat")
@limiter.limit_ws("30/minute")  # 30 messages per minute
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        # ... process message ...
        await websocket.send_text(f"Echo: {data}")
```

---

## Reverse Proxy Deployment

Running drogue behind Nginx, Traefik, or Cloudflare.

### Strategy

- Configure trusted proxies
- Read real client IP from `X-Forwarded-For`
- Prevent header spoofing

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Drogue Configuration

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter

app = FastAPI()
limiter = DrogueLimiter(
    app,
    trusted_proxies=["127.0.0.1", "10.0.0.0/8"]
)
```

### Cloudflare

When using Cloudflare, configure drogue to trust Cloudflare IP ranges:

```python
# Cloudflare IPv4 ranges
CLOUDFLARE_IPS = [
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
]

limiter = DrogueLimiter(
    app,
    trusted_proxies=CLOUDFLARE_IPS
)
```

---

## Microservices Rate Limiting

Rate limiting internal service-to-service communication.

### Strategy

- Per-service rate limits
- Service identity extraction
- Centralized or distributed rate limiting

### FastAPI Example

```python
from fastapi import FastAPI, Request
from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.identity import HeaderExtractor

app = FastAPI()
limiter = DrogueLimiter(
    app,
    key_func=HeaderExtractor("X-Service-Name")  # Identify by service name
)

@app.get("/api/internal/data")
@limiter.limit("1000/minute")  # 1000 requests per minute per service
async def internal_data():
    return {"data": "value"}

@app.get("/api/internal/heavy")
@limiter.limit("100/minute", cost=5)  # Expensive endpoint
async def heavy_internal():
    # ... complex computation ...
    return {"result": "value"}
```

### Multi-Tenant SaaS

```python
from fastapi import FastAPI, Request
from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.identity import HeaderExtractor

app = FastAPI()
limiter = DrogueLimiter(
    app,
    key_func=HeaderExtractor("X-Tenant-ID")  # Identify by tenant
)

@app.get("/api/tenant/data")
@limiter.limit("5000/hour")  # Per-tenant limit
async def tenant_data():
    return {"data": "value"}
```

---

## Summary

| Scenario | Key Extractor | Rate Limit | Protection Layer |
|----------|---------------|------------|------------------|
| Login | IP | 5/minute | Brute force |
| API Key | Header | 1000/day | Abuse |
| WebSocket | Connection | 30/minute | Real-time abuse |
| Reverse Proxy | X-Forwarded-For | Per-client | Network layer |
| Microservices | Service name | Per-service | Internal abuse |
