# Changelog

## 0.4.0

### Added

- Challenges (CAPTCHA escalation) for page traffic: Turnstile provider, pluggable `ChallengeProvider` protocol, signed pass cookies, single-use token claims, verify-endpoint rate limiting, failure escalation into auto-ban and trust (`docs/protection/challenges.md`)
- New optional dependency extra: `pip install drogue[turnstile]` (httpx)
- Circuit breaker fed by 5xx responses from FastAPI traffic
- `DROGUE_STORAGE` setting for the DRF throttle to share Redis storage

### Fixed

- FastAPI routes declaring `request: Request` no longer 500 (the limiter decorator kept the injected request)
- Stacked `@limiter.limit` decorators no longer double-count on FastAPI and Flask
- Shadow-mode and CIDR-deny requests no longer crash with a `TypeError` (500)
- MongoDB backend: `compare_and_swap` create-if-absent now works (algorithms no longer deny all traffic), expiry is stored as UTC datetimes so the TTL index is effective, duplicate-key races are handled
- Sliding/fixed window algorithms wrap backend outages in `BackendFailure` like the other algorithms, and blocking mode now honors the `timeout` deadline
- Trusted-proxy matching supports CIDR entries and IPv4-mapped IPv6 addresses
- `Retry-After` is a positive integer for sub-second waits, and 429 bodies no longer show negative `remaining`
- Challenge pass cookies honor `challenge_cookie_secure`; open-redirect `next` values with backslashes are neutralized; denials carry `Retry-After` headers
- Per-endpoint WebSocket limits (shared `"ws"` bucket split by route)

## 0.3.0

- Protection pipeline wiring, defense features shipped to production paths
- MongoDB storage backend (Motor async driver), `pip install drogue[mongodb]`
- GCRA and Leaky Bucket algorithms, thread-safe CAS in all 5 algorithms
- Trust state machine, progressive auto-ban, DDoS Z-score, probe detection, sentinel model, shadow mode

### Known limitations

- Redis-backed state stores `time.monotonic()`-derived timestamps, which is only correct on a single host; multi-host Redis deployments need epoch-based state (planned for 0.4.1)
- Adaptive limits and trust multipliers create a fresh counter key per effective limit, granting a full new quota on each adjustment
- The probe detector can be tripped by ordinary 404 bursts (3 unique 404s inside a minute); tune with `probes_enabled=False` or pin behind a reverse proxy that drains assets

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
