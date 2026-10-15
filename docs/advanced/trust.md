# Trust State Machine

## Overview

The Trust State Machine implements tiered processing where trusted users skip expensive evaluation steps, dramatically improving throughput.

## How It Works

**Trust states:**

```
UNKNOWN -> [first request, full evaluation] -> EVALUATED
EVALUATED -> [score < 0.2] -> TRUSTED (cached 4h)
EVALUATED -> [score 0.2-0.5] -> STANDARD (cached 30min)
EVALUATED -> [score > 0.5] -> SUSPICIOUS (never cached)

TRUSTED -> [any anomaly] -> POISONED -> UNKNOWN
TRUSTED -> [4h elapsed] -> UNKNOWN (re-evaluate)
```

## Usage

```python
from drogue.protection.trust import TrustManager, TrustLevel

trust = TrustManager(
    trusted_ttl=14400,  # 4 hours
    standard_ttl=1800,  # 30 minutes
    score_threshold_trusted=0.2,
    score_threshold_standard=0.5,
    max_fingerprints=100_000,
)

# Check trust level
level = trust.check("fingerprint_abc123")
if level == TrustLevel.TRUSTED:
    # Skip everything (~5 microseconds)
    return RateLimitResult(allowed=True, tier=0)

# Update trust after full evaluation
score = compute_trust_score(context, result)
trust.update("fingerprint_abc123", score)

# Instant invalidation on anomaly
trust.poison("fingerprint_abc123")
```

## Integration with drogue

Trust is wired into the pipeline and the FastAPI adapter. The pipeline
tracks consecutive successes per key and promotes clean clients to
TRUSTED; any violation poisons trust immediately. Trusted keys are
never exempt from rate limiting, but the adapter rewards them with a
higher effective limit.

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    trust_enabled=True,
    trust_success_threshold=100,  # successes before promotion
    trust_limit_multiplier=2.0,   # TRUSTED keys get 2x the limit
)
limiter = DrogueLimiter(FastAPI(), config=config)
```

Manual wiring through your own pipeline works the same way:

```python
from drogue.protection import ProtectionPipeline, TrustManager

trust = TrustManager()
pipeline = ProtectionPipeline(trust=trust, trust_success_threshold=100)

await pipeline.check(key, context)   # consults nothing; trust never blocks
pipeline.record_success(key)         # streak += 1, maybe promotes
pipeline.record_violation(key)       # poisons + resets the streak
trust.is_trusted(key)                # True once promoted
```

## Performance Impact

| Trust Level | Latency | Throughput |
|-------------|---------|------------|
| UNKNOWN | ~200 microseconds | 5K req/s |
| STANDARD | ~43 microseconds | 23K req/s |
| TRUSTED | ~5 microseconds | 200K req/s |

**Impact:** 60-70% of requests go from ~43 microseconds to ~5 microseconds (9x improvement).

## Configuration

```python
trust = TrustManager(
    max_fingerprints=100_000,      # Maximum cached fingerprints
    trusted_ttl=14400,             # 4 hours
    standard_ttl=1800,             # 30 minutes
    score_threshold_trusted=0.2,   # Score below which fingerprint is TRUSTED
    score_threshold_standard=0.5,  # Score below which fingerprint is STANDARD
)
```

## Statistics

```python
stats = trust.get_stats()
# {
#     "total_checks": 10000,
#     "trusted_hits": 7000,
#     "standard_hits": 2000,
#     "unknown_misses": 1000,
#     "poison_count": 5,
#     "trusted_rate": 0.7,
#     "cached_fingerprints": 50000,
#     "max_fingerprints": 100000,
# }
```

## Poison Pill

When an anomaly is detected, the fingerprint is instantly invalidated:

```python
# Anomaly detected
trust.poison("fingerprint_abc123")

# All subsequent requests hit full pipeline
level = trust.check("fingerprint_abc123")
# Returns TrustLevel.UNKNOWN
```

**Attack scenario:**

1. Attacker spoofs trusted fingerprint
2. First anomalous request poisons the cache
3. All subsequent requests hit full pipeline
4. Cost: one anomalous request slips through (low damage)
5. Benefit: 10,000x reduction in processing for real users
