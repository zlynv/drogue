# Trust State Machine

## What is the trust system?

The trust system tracks client behavior over time and assigns trust levels. Trusted clients get faster processing (skip some checks), while suspicious clients face stricter scrutiny. This creates a "fast path" for verified users.

## Why it matters

Without trust differentiation, every request goes through the same evaluation path. This wastes resources on known-good clients and doesn't catch clients that gradually become malicious.

## Trust levels

| Level | Score range | What it means | Behavior |
|-------|-------------|---------------|----------|
| TRUSTED | score < 0.2 | Verified, good history | Fast-tracked, minimal checks |
| STANDARD | 0.2 <= score < 0.5 | Normal, no issues | Standard rate limiting |
| SUSPICIOUS | 0.5 <= score < 1.0 | Some bad behavior | Additional scrutiny |
| BANNED | score >= 1.0 | Confirmed threat | Blocked |

## How scoring works

```
Each request updates the trust score:
- Successful request: score decreases (more trusted)
- Failed request: score increases (less trusted)
- Anomaly detected: score increases more

The score is bounded between 0.0 and 1.0.
```

## Usage

```python
from drogue.protection.trust import TrustManager

manager = TrustManager()

# Update trust score (negative = good, positive = bad)
level = manager.update("fingerprint_abc", score=-0.1)
# TrustLevel.TRUSTED (score went down)

level = manager.update("fingerprint_abc", score=0.3)
# TrustLevel.SUSPICIOUS (score went up)

# Check trust level
level = manager.check("fingerprint_abc")
# TrustLevel.TRUSTED / STANDARD / SUSPICIOUS / BANNED

# Get full state
state = manager.get_state("fingerprint_abc")
# TrustState(level=TrustLevel.STANDARD, score=0.5, created_at=..., expires_at=..., ...)
```

## Response examples

### `get_state()` response

```python
state = manager.get_state("fingerprint_abc")
# TrustState(
#     level=<TrustLevel.STANDARD: 'standard'>,
#     created_at=1690000000.0,
#     expires_at=1690003600.0,   # TTL expiry (or None)
#     score=0.35,
#     request_count=150,
#     anomaly_count=2,
# )
```

### `get_stats()` response

```python
stats = manager.get_stats()
# {
#     "total_fingerprints": 1500,
#     "trusted": 200,
#     "standard": 1100,
#     "suspicious": 150,
#     "banned": 50,
# }
```

## Manual operations

```python
# Ban a client manually
manager.ban("fingerprint_abc")

# Poison (mark as known threat)
manager.poison("fingerprint_abc")

# Check if banned
is_banned = manager.is_banned("fingerprint_abc")  # True

# Check if trusted
is_trusted = manager.is_trusted("fingerprint_abc")  # False

# Clear all trust data
count = manager.clear()  # Returns number of cleared entries
```

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    trust_enabled=True,
    trust_max_fingerprints=100000,
    trust_trusted_ttl=14400.0,      # 4 hours
    trust_standard_ttl=1800.0,       # 30 minutes
    trust_score_threshold_trusted=0.2,
    trust_score_threshold_standard=0.5,
)
```

## Integration example

```python
from drogue.protection.trust import TrustManager

manager = TrustManager()

# On each request
def handle_request(fingerprint, success):
    level = manager.update(fingerprint, score=-0.1 if success else 0.1)

    if level == TrustLevel.TRUSTED:
        # Fast path: skip expensive checks
        return fast_response()
    elif level == TrustLevel.BANNED:
        # Block immediately
        return blocked_response()
    else:
        # Standard path: full rate limiting
        return rate_limited_response()
```
