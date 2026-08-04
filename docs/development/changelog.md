# Changelog

## [0.2.0] - 2026-08-02

### Added

#### Core Engine
- GCRA (Generic Cell Rate Algorithm) for telecom-grade smooth traffic
- Leaky Bucket algorithm for constant-rate traffic
- All 5 algorithms now support thread-safe CAS operations

#### Storage
- MongoDB storage backend using Motor async driver
- TTL index for automatic key expiry
- `pip install drogue[mongodb]` for MongoDB support

#### Testing
- Thread safety tests proving drogue is thread-safe under concurrent access
- 174 unit tests passing (up from 131)
- Benchmark suite with function-level and HTTP load tests
- Locust load testing for throughput and latency measurement

#### Documentation
- CDN vs Library-Level protection guide
- All 5 algorithms documented with visual ASCII diagrams
- Benchmark documentation with results
- Google site verification for SEO

#### Adapters
- Flask headers bug fixed — now works for dict-returning views
- Flask adapter uses `after_request` hook instead of broken `hasattr` approach

### Changed
- Navigation reorganized from 14 to 10 tabs (merged related pages)
- Algorithm comparison table updated with all 5 algorithms
- README updated with benchmark results

### Known Limitations
- Ban state is in-memory only (Redis persistence planned for v0.3)
- Trust cache is per-process (multi-worker needs separate state)

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
- Trust State Machine with 5 states (UNKNOWN → TRUSTED/STANDARD/SUSPICIOUS/BANNED)
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

## [0.3.0] - Planned

### Planned
- WebSocket support for Django and Flask
- Redis-backed ban state persistence
- Trust cache cross-process sync
- Advanced probe detection patterns
