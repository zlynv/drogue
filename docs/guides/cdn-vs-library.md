---
description: CDN vs library-level rate limiting. When to use Cloudflare/AWS WAF vs drogue for API protection.
---

# CDN vs Library-Level Protection

CDN-level protection (Cloudflare, AWS WAF, Akamai) and library-level protection (drogue) solve different problems. They are complementary, not competing.

## What CDN Does

CDN stops floods at the edge, before traffic reaches your server.

| Capability | CDN | drogue |
|------------|-----|--------|
| Volumetric DDoS (L3/L4) | Yes | No |
| HTTP flood (L7) | Yes | Yes |
| Global traffic visibility | Yes | No |
| Hardware-level absorption (Tbps) | Yes | No |
| Bot behavioral scoring (ML) | Yes | No |
| Managed threat intelligence | Yes | No |
| CAPTCHA/JS challenges | Yes | No |
| Zero application changes | Yes | No |

## What drogue Does That CDN Can't

CDN sees IP addresses and HTTP headers. drogue sees your application logic.

| Capability | CDN | drogue |
|------------|-----|--------|
| Rate limit by **user ID** | No | Yes |
| Rate limit by **account tier** | No | Yes |
| Rate limit by **subscription level** | No | Yes |
| Endpoint-specific rules with custom logic | No | Yes |
| Internal service protection (microservices) | No | Yes |
| WebSocket rate limiting | Limited | Yes |
| Trust-based rate limiting | No | Yes |
| Circuit breaker for backend failures | No | Yes |
| Adaptive limits under system load | No | Yes |
| Shadow mode (test without enforcement) | No | Yes |
| No vendor lock-in | No | Yes |

## When to Use CDN

Use CDN-level protection when:

- You need to stop volumetric DDoS attacks (millions of requests per second)
- You want zero application code changes
- You need global traffic visibility across multiple domains
- You want managed threat intelligence and bot detection
- You need SLA-backed protection guarantees

## When to Use drogue

Use library-level protection when:

- You need to rate limit by **business identity** (user ID, account tier, API key)
- You have **endpoint-specific rules** (login: 5/min, API: 100/min, search: 10/min)
- You need to protect **internal microservices** from each other
- You want **trust-based rate limiting** (verified users get higher limits)
- You need **circuit breaker** patterns for downstream services
- You want **adaptive limits** that scale with system load
- You need **shadow mode** to test rules before enforcement
- You want **no vendor lock-in** (works with any hosting provider)

## The Ideal Setup

Use both together:

```
Internet → CDN (Cloudflare/AWS WAF) → Your Server (drogue) → Application
```

1. **CDN** stops volumetric attacks and known malicious IPs at the edge
2. **drogue** handles application-level rate limiting by user identity
3. **drogue** protects against attacks that bypass CDN (valid IPs, API key abuse)
4. **drogue** provides trust-based limits, circuit breakers, and adaptive behavior

## Example: Cloudflare + drogue

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter

app = FastAPI()

# Cloudflare stops volumetric DDoS
# drogue handles application-level rate limiting by user ID
limiter = DrogueLimiter(
    app,
    rules=["100/minute"],
    trusted_proxies=[
        "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22",
        # ... Cloudflare IP ranges
    ],
)

@app.get("/api/data")
@limiter.limit("10/second")
async def get_data():
    return {"data": "value"}
```

## Cost Comparison

| Solution | Cost | Protection Level |
|----------|------|------------------|
| Cloudflare Free | $0/month | Basic DDoS, CDN |
| Cloudflare Pro | $20/month | Advanced DDoS, WAF |
| AWS WAF | ~$5/month + $0.60/million requests | Rate limiting, bot control |
| drogue | Free (open source) | Application-level rate limiting |
| drogue + Redis | Free + Redis cost | Distributed rate limiting |

## Summary

- **CDN** = infrastructure protection (stops floods at edge)
- **drogue** = application protection (rate limits by identity, adapts to load)
- **Use both** for defense in depth
