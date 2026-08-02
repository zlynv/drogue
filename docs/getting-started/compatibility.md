# Compatibility Matrix

drogue supports multiple Python versions, frameworks, and storage backends. This page shows what is supported and the maturity level of each component.

---

## Python Versions

| Version | Status | Notes |
|---------|--------|-------|
| Python 3.10 | Stable | Minimum supported version |
| Python 3.11 | Stable | |
| Python 3.12 | Stable | |
| Python 3.13 | Stable | Latest tested version |

---

## Framework Adapters

| Framework | Status | Min Version | Extra | Notes |
|-----------|--------|-------------|-------|-------|
| FastAPI | Stable | >=0.100.0 | `drogue[fastapi]` | ASGI, full feature set, WebSocket support |
| Flask | Stable | >=3.0.0 | `drogue[flask]` | WSGI, sync adapter, decorator-based |
| Django | Stable | >=4.2 | `drogue[django]` | Middleware + decorator |
| Django REST Framework | Stable | >=3.14 | `drogue[drf]` | Throttle adapter |

### Framework Feature Matrix

| Feature | FastAPI | Flask | Django | DRF |
|---------|---------|-------|--------|-----|
| Decorator-based limiting | Yes | Yes | Yes | Yes |
| Global middleware | Yes | Yes | Yes | Yes |
| WebSocket support | Yes | No | No | No |
| Dependency injection | Yes | No | No | No |
| Async support | Native | Bridge | Native | Native |
| Header injection | Auto | Auto | Auto | Auto |

---

## Storage Backends

| Backend | Status | Extra | Notes |
|---------|--------|-------|-------|
| Memory | Stable | — | Default, in-process, lost on restart |
| Redis | Stable | `drogue[redis]` | Recommended for production, supports clustering |
| MongoDB | Alpha | `drogue[mongodb]` | Uses Motor async driver, TTL indexes |

### Storage Feature Matrix

| Feature | Memory | Redis | MongoDB |
|---------|--------|-------|---------|
| Atomic operations | Yes | Yes | Yes |
| TTL support | Yes | Yes | Yes |
| Persistence | No | Yes | Yes |
| Multi-process | No | Yes | Yes |
| Clustering | No | Yes | Yes |
| Async | Native | Native | Native (Motor) |

---

## Protection Features

| Feature | Status | Notes |
|---------|--------|-------|
| Rate limiting | Stable | All 5 algorithms |
| DDoS detection | Stable | Z-score anomaly detection |
| Progressive auto-ban | Stable | 5 escalating levels |
| Trust state machine | Stable | 7 states |
| Circuit breaker | Stable | Closed/Open/HalfOpen |
| Adaptive limits | Stable | CPU/memory-aware |
| CIDR filtering | Stable | IPv4 and IPv6 |
| Probe detection | Stable | |
| Defense randomization | Stable | |
| Shadow mode | Stable | Test rules without enforcement |
| Sentinel model | Alpha | Streaming anomaly detection |
| Honeypots | Alpha | Decoy endpoints |

---

## Observability

| Feature | Status | Notes |
|---------|--------|-------|
| Prometheus metrics | Stable | |
| Structured logging | Stable | JSON format |
| OpenTelemetry tracing | Stable | |

---

## Installation

```bash
pip install drogue

# With framework extras
pip install drogue[fastapi]   # FastAPI + Starlette
pip install drogue[django]    # Django
pip install drogue[flask]     # Flask
pip install drogue[drf]       # Django REST Framework
pip install drogue[redis]     # Redis backend
pip install drogue[mongodb]   # MongoDB backend
pip install drogue[all]       # Everything
```

---

## CI/CD Matrix

drogue is tested in CI against:

| Component | Versions |
|-----------|----------|
| Python | 3.10, 3.11, 3.12, 3.13 |
| OS | Ubuntu latest |
| FastAPI | Latest compatible |
| Flask | Latest compatible |
| Django | Latest compatible |
| DRF | Latest compatible |

All combinations are tested on every push and pull request.
