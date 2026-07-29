# Cloudflare Proxy Setup

When your application is behind Cloudflare, all traffic appears to come from Cloudflare's edge IPs. drogue needs to be configured to trust Cloudflare's `X-Forwarded-For` header to extract the real client IP.

## The Problem

Without configuration, drogue sees every request as coming from a Cloudflare IP (e.g., `104.16.0.1`). All users share the same rate limit key, which defeats the purpose.

## The Solution

Cloudflare sets the `X-Forwarded-For` header with the real client IP. drogue reads this header by default, but you must tell it to trust the header value by adding Cloudflare's IP ranges to `trusted_proxies`.

## FastAPI

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter

app = FastAPI()

# Cloudflare IPv4 ranges
CLOUDFLARE_IPV4 = [
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

# Cloudflare IPv6 ranges
CLOUDFLARE_IPV6 = [
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
]

CLOUDFLARE_RANGES = CLOUDFLARE_IPV4 + CLOUDFLARE_IPV6

limiter = DrogueLimiter(
    app,
    storage="memory://",
    rules=["100/minute"],
    trusted_proxies=CLOUDFLARE_RANGES,
)

@app.get("/api/data")
@limiter.limit("10/second")
async def get_data():
    return {"data": "value"}
```

## Django

```python
# settings.py
DROGUE_CONFIG = {
    "trusted_proxies": [
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
    ],
}
```

## Flask

```python
from flask import Flask
from drogue.adapters.flask import DrogueLimiter

app = Flask(__name__)

CLOUDFLARE_RANGES = [
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
    storage="memory://",
    rules=["100/minute"],
    trusted_proxies=CLOUDFLARE_RANGES,
)
```

## Reusable Helper

Create a helper to avoid repeating the ranges:

```python
# cloudflare.py
CLOUDFLARE_RANGES = [
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
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
]
```

```python
from cloudflare import CLOUDFLARE_RANGES
from drogue.adapters.fastapi import DrogueLimiter

limiter = DrogueLimiter(
    app,
    storage="memory://",
    rules=["100/minute"],
    trusted_proxies=CLOUDFLARE_RANGES,
)
```

## How It Works

1. Client sends request to `your-site.com`
2. Cloudflare receives request, adds `X-Forwarded-For: 203.0.113.50`
3. Cloudflare forwards to your origin server
4. drogue reads `X-Forwarded-For` header
5. drogue checks if the connecting IP (Cloudflare edge) is in `trusted_proxies`
6. If trusted, uses the rightmost untrusted IP (`203.0.113.50`) as client IP
7. Rate limiting uses the real client IP

## Verifying It Works

Test with a request that includes the header:

```bash
curl -H "X-Forwarded-For: 203.0.113.50" http://localhost:8000/api/data
```

The rate limit should apply to `203.0.113.50`, not the Cloudflare edge IP.

## Common Issues

### All users share one limit

**Cause**: `trusted_proxies` not configured. drogue uses the connecting IP (Cloudflare edge).

**Fix**: Add Cloudflare IP ranges to `trusted_proxies`.

### Wrong client IP detected

**Cause**: Cloudflare not setting `X-Forwarded-For` correctly, or your origin server strips the header.

**Fix**: Check Cloudflare dashboard → Network → IP Headers. Ensure "Preserve all IP headers" is enabled.

### Rate limit too strict

**Cause**: Cloudflare makes multiple connections for a single client request (e.g., HTTP/2, WebSocket upgrades).

**Fix**: Increase limits slightly, or use `key_func` to identify by user rather than IP.

### IPv6 not working

**Cause**: Only IPv4 ranges configured, client connects via IPv6.

**Fix**: Add Cloudflare IPv6 ranges to `trusted_proxies`.

## Cloudflare IP Ranges (Updated)

Cloudflare publishes their IP ranges at:
https://www.cloudflare.com/ips/

The ranges in this guide were last verified in 2026. For the latest ranges, check the Cloudflare documentation.
