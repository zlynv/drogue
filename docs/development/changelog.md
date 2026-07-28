# Changelog

## [0.1.0] - 2026-01-XX

### Added

#### Core Engine
- Token Bucket algorithm with leaky bucket semantics
- Sliding Window algorithm for precise rate limiting
- Fixed Window algorithm for lowest memory usage
- Rate limit string parser (`100/minute`, `10/second;50/minute`)
- Thread-safe MemoryStorage backend
- RedisStorage backend for distributed deployments
- Cost-aware rate limiting
- Identity extractors (IP, user, header, path, static, composite)
- Anti-spoof X-Forwarded-For handling
- Configurable fail-closed behavior

#### Adapters
- FastAPI adapter with decorator and dependency injection
- Django adapter with middleware and view decorators
- Flask adapter with decorator support
- Django REST Framework (DRF) throttle adapter
- WebSocket rate limiting (FastAPI)
- Automatic rate limit header injection

#### Protection Layer
- Progressive auto-ban with escalating durations
- DDoS detection using Z-score anomaly analysis
- WebSocket DDoS detection
- Trust State Machine with 7 states (UNKNOWN → TRUSTED)
- Sentinel Model (Half-Space Trees) for streaming anomaly detection
- Probe Pattern Detector for early attack warning
- CIDR filtering with IPv4/IPv6 support
- Adaptive rate limiting based on system metrics

#### Defense
- Defense Randomization (game-theoretic)
- Honeypot Manager for bot detection
- Challenge types: JS PoW, Cookie, CAPTCHA, Canary

#### Storage
- Count-Min Sketch (80x memory reduction)
- Bloom Filter for set membership
- Cuckoo Filter with deletion support
- HyperLogLog for unique visitor counting

#### Observability
- Prometheus metrics export
- OpenTelemetry tracing and metrics
- Structured logging

#### Testing
- 131 unit tests passing
- 36 integration tests (FastAPI + Django)
- 14 regression tests
- Token bucket leak fix regression test

### Fixed
- Token bucket fractional truncation bug causing infinite token leak
- `BackendFailure` missing `message` attribute
- FastAPI ASGI middleware not wrapping `receive`/`send`
- `__signature__` injection preventing FastAPI introspection
- Storage identity bug (`bool(MemoryStorage())` is False)
- Multi-rule key collision in FastAPI adapter
- Django `ROOT_URLCONF` configuration
- Circuit breaker assertion timing
- Test isolation between storage backends

### Known Limitations
- Ban state is in-memory only (Redis persistence planned for v0.3)
- Trust cache is per-process (multi-worker needs separate state)
- Flask header injection for dict-returning views doesn't work

## [0.2.0] - Planned

### Planned
- WebSocket support for Django and Flask
- Redis-backed ban state persistence

## [0.3.0] - Planned

### Planned
- Trust cache cross-process sync
- Advanced probe detection patterns
