# Changelog

## 0.2.0

- Added GCRA and Leaky Bucket algorithms (5 total)
- ProtectionPipeline: unified ban → DDoS → circuit breaker pipeline
- Flask headers bug fixed (after_request hook)
- Thread safety tests for all algorithms
- DDoS detector Z-score fix: compares across client rate distribution
- Trust state machine cleanup (removed dead EVALUATED/POISONED states)
- Progressive ban: 4 levels (1min → 10min → 1hr → 24hr)
- CI workflow with Codecov integration
- Documentation site with security model, real-world examples, compatibility matrix

## 0.1.1

- Fix README accuracy: memory claims, author consistency, broken links
- Add Flask and DRF optional dependencies to pyproject.toml
- Add LICENSE file (MIT)
- Add documentation site

## 0.1.0

Initial release.

### Core

- Token Bucket, Sliding Window, Fixed Window algorithms
- Rate limit string parser (`100/minute`, `10/second;50/minute`)
- MemoryStorage and RedisStorage backends
- Identity extractors (IP, user, header, path, static, composite)
- Cost-aware rate limiting
- Anti-spoof X-Forwarded-For handling

### Adapters

- FastAPI: ASGI middleware, decorators, dependency injection, WebSocket
- Django: middleware, decorators, DRF throttle
- Flask: decorators, before_request hook

### Protection

- DDoS detection (Z-score anomaly analysis)
- Progressive auto-ban with escalating durations
- Trust state machine with LRU cache
- Circuit breaker with jitter
- Probe pattern detection
- CIDR filtering (IPv4/IPv6)
- Adaptive rate limiting (CPU, memory, latency)

### Defense

- Per-session defense randomization
- Honeypot management

### Storage

- Count-Min Sketch (10MB for 1M keys)
- Bloom Filter, Cuckoo Filter, HyperLogLog

### Observability

- Prometheus metrics
- OpenTelemetry tracing and metrics
- Structured JSON logging
