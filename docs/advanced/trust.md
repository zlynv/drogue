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

```python
class DrogueLimiter:
    async def _check(self, context):
        fingerprint = context.identity.fingerprint

        # Tier 0: Trusted -- skip everything
        if self.trust_manager and self.trust_manager.is_trusted(fingerprint):
            return RateLimitResult(allowed=True, tier=0)

        # Tier 1: Standard -- rate limit only
        result = await self._check_algorithm(context)

        # After check: update trust score
        if self.trust_manager:
            score = self._compute_trust_score(context, result)
            self.trust_manager.update(fingerprint, score)

        return result
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
