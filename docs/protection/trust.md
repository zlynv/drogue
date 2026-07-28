# Trust State Machine

## How it works

Each client fingerprint gets a trust score. The score increases with good behavior and decreases with bad behavior. Based on the score, clients are classified into trust levels.

## Trust levels

| Level | Score range | Behavior |
|-------|-------------|----------|
| TRUSTED | score < 0.2 | Fast-tracked, minimal checks |
| STANDARD | 0.2 <= score < 0.5 | Normal rate limiting |
| SUSPICIOUS | 0.5 <= score < 1.0 | Additional scrutiny |
| BANNED | score >= 1.0 or manual | Blocked |

## Usage

```python
from drogue.protection.trust import TrustManager

manager = TrustManager()

# Update trust score (negative = suspicious, positive = good)
level = manager.update("fingerprint_abc", score=-0.1)
# TrustLevel.TRUSTED

# Check trust level
level = manager.check("fingerprint_abc")

# Get full state
state = manager.get_state("fingerprint_abc")
# TrustState(level=TrustLevel.STANDARD, score=0.5, ...)

# Quick checks
assert manager.is_trusted("fingerprint_abc") == True
assert manager.is_banned("fingerprint_abc") == False

# Manual ban/unban
manager.ban("fingerprint_abc")
manager.poison("fingerprint_abc")  # mark as threat

# Stats
stats = manager.get_stats()
```

## Standalone usage

```python
from drogue.protection.trust import TrustManager

manager = TrustManager(
    max_fingerprints=100000,
    trusted_ttl=14400.0,       # 4 hours
    standard_ttl=1800.0,       # 30 minutes
    score_threshold_trusted=0.2,
    score_threshold_standard=0.5,
)
```
