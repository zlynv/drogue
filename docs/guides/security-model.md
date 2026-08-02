# Security Model

This page explains what drogue protects against, what it does not, and how to integrate it into a broader security strategy.

---

## What Drogue Protects Against

Drogue is an **application-layer protection library**. It defends against abuse and attacks that target your API endpoints.

### DDoS Attacks

| Attack Type | Protection |
|-------------|------------|
| Volumetric (flood) | Rate limiting per client key |
| Slowloris / slow POST | Connection-level rate limits |
| Resource exhaustion | Adaptive limits (CPU/memory-aware) |
| Distributed (botnet) | Z-score anomaly detection |

### Abuse and Over-Use

| Attack Type | Protection |
|-------------|------------|
| Brute force (login) | Per-IP and per-user rate limits |
| Credential stuffing | Progressive bans + trust state machine |
| API key abuse | Per-key quotas and cost-based limits |
| Scraping / harvesting | Rate limiting + probe detection |
| Bot traffic | Anomaly detection + defense randomization |

### Distributed Attacks

Drogue's key differentiator: it catches attacks where each client stays under the individual rate limit.

- 50,000 IPs each sending 10 req/min = 500,000 req/min total
- Traditional rate limiters see nothing wrong (each client is under limit)
- Drogue's Z-score detector flags the anomalous traffic pattern

---

## Threats Drogue Intentionally Does Not Solve

Drogue is **not** a general security framework. It handles rate limiting and application-layer protection. You still need:

| Threat | Why Drogue Doesn't Solve It | What to Use Instead |
|--------|-----------------------------|---------------------|
| **SQL Injection** | Drogue doesn't inspect request bodies or query parameters | Parameterized queries, ORMs (SQLAlchemy, Django ORM) |
| **XSS** | Drogue doesn't sanitize output | Output encoding, CSP headers, DOMPurify |
| **CSRF** | Drogue doesn't validate request origin | CSRF tokens, SameSite cookies, double-submit pattern |
| **RCE** | Drogue doesn't sandbox code execution | Input validation, containerization, least privilege |
| **Authentication** | Drogue doesn't verify identity | OAuth 2.0, JWT, session tokens, proper auth frameworks |
| **Authorization** | Drogue doesn't enforce permissions | RBAC/ABAC, permission classes, policy engines |
| **Encryption** | Drogue doesn't encrypt data in transit or at rest | TLS (HTTPS), encrypted storage, envelope encryption |
| **Secrets Management** | Drogue doesn't manage secrets | HashiCorp Vault, AWS Secrets Manager, env vars |
| **Input Validation** | Drogue doesn't validate request schemas | Pydantic, marshmallow, Django REST serializer validation |
| **Business Logic** | Drogue doesn't enforce business rules | Custom middleware, domain-specific validation |

!!! warning "Drogue is not a WAF"
    Drogue replaces application-layer rate limiting. It does not replace a Web Application Firewall (WAF) like Cloudflare, AWS WAF, or ModSecurity. Use both.

---

## Security Boundaries and Assumptions

### Trust Model

Drogue's trust state machine assumes:

- **New clients** start as "Unknown" and get conservative limits
- **Verified clients** can be promoted to "Trusted" with higher limits
- **Suspicious clients** get degraded limits
- **Banned clients** are blocked entirely

The trust model is per-process by default. In multi-worker deployments, each worker maintains its own trust state.

### Proxy Header Handling

When running behind a reverse proxy (Nginx, Traefik, Cloudflare):

- Drogue reads `X-Forwarded-For` and `X-Real-IP` headers
- You **must** configure trusted proxies to prevent header spoofing
- If an attacker can set `X-Forwarded-For` to a trusted IP, they can bypass rate limits

```python
# Only trust headers from your proxy
limiter = DrogueLimiter(
    app,
    trusted_proxies=["10.0.0.0/8", "172.16.0.0/12"]
)
```

### Storage Security

| Backend | Security Consideration |
|---------|----------------------|
| **Memory** | Data is lost on restart. No network exposure. |
| **Redis** | Use TLS, authentication, and network isolation |
| **MongoDB** | Use authentication, TLS, and network isolation |

### Rate Limit Bypass Risks

Attackers may try to bypass rate limits by:

- Rotating IP addresses (partially mitigated by trust state)
- Using different API keys (mitigated by per-key limits)
- Spoofing proxy headers (mitigated by trusted proxy config)
- Exploiting race conditions (mitigated by atomic storage operations)

---

## Recommended Security Stack

Drogue handles one layer of your security. For production applications, use:

```
┌─────────────────────────────────────────────────┐
│  Cloudflare / AWS WAF / ModSecurity             │  ← Network layer DDoS
├─────────────────────────────────────────────────┤
│  Nginx / Traefik / HAProxy                      │  ← Reverse proxy, TLS
├─────────────────────────────────────────────────┤
│  Drogue                                        │  ← Rate limiting, app-layer DDoS
├─────────────────────────────────────────────────┤
│  Auth Framework (OAuth, JWT, session)          │  ← Authentication
├─────────────────────────────────────────────────┤
│  Permission Framework (RBAC, ABAC)             │  ← Authorization
├─────────────────────────────────────────────────┤
│  Input Validation (Pydantic, ORM)              │  ← SQL injection, XSS
├─────────────────────────────────────────────────┤
│  Your Application                              │  ← Business logic
└─────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Handles | Example Tools |
|-------|---------|---------------|
| Network DDoS | Volumetric floods, SYN floods | Cloudflare, AWS Shield, Nginx |
| Reverse Proxy | TLS termination, request routing | Nginx, Traefik, HAProxy |
| **Drogue** | **Rate limiting, application-layer DDoS, abuse** | **drogue** |
| Authentication | Identity verification | Authlib, Django auth, Passport.js |
| Authorization | Permission enforcement | Casbin, Django permissions |
| Input Validation | Schema enforcement, injection prevention | Pydantic, marshmallow |

---

## Vulnerability Disclosure

If you discover a security vulnerability in drogue, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Use [GitHub's private vulnerability reporting](https://github.com/zlynv/drogue/security/advisories/new)
3. Include: description, steps to reproduce, potential impact
4. Response time: 48 hours

See [SECURITY.md](https://github.com/zlynv/drogue/blob/main/SECURITY.md) for full disclosure policy.
