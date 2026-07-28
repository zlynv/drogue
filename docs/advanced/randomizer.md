# Defense Randomization

## Overview

Defense Randomization prevents attackers from learning and adapting to exact thresholds by randomizing defense parameters per-session.

## How It Works

Instead of fixed rate limits (e.g., exactly 100/min), each session gets a randomized limit within a range (e.g., 80-120/min). This creates uncertainty for attackers probing the system's boundaries.

## Usage

```python
from drogue.defense.randomizer import DefenseRandomizer, ChallengeType

randomizer = DefenseRandomizer(
    rate_limit_range=(80, 120),        # 80-120% of base limit
    challenge_types=[ChallengeType.JS_POW, ChallengeType.COOKIE],
    pow_difficulty_range=(18, 24),      # 18-24 bits
    response_jitter_range=(0, 200),     # 0-200ms delay
)

# Get randomized limit for session
effective_limit = randomizer.get_effective_limit("session_abc123", 100)
# Returns value between 80-120

# Apply jitter to suspicious responses
randomizer.apply_jitter("session_abc123", response)
```

## Why It Works

**User A sees:** rate limit = 95/min (randomized)
**User B sees:** rate limit = 107/min (different)
**User C sees:** rate limit = 82/min (different)

**Attacker targeting "exactly 100/min" gets caught by A and C.**

## Configuration

```python
randomizer = DefenseRandomizer(
    rate_limit_range=(80, 120),        # Min/max rate limit multiplier
    challenge_types=[...],              # Available challenge types
    pow_difficulty_range=(18, 24),      # Min/max PoW difficulty
    response_jitter_range=(0, 200),     # Min/max response jitter (ms)
    session_ttl=3600.0,                 # Session TTL (seconds)
    max_sessions=100_000,               # Maximum sessions to track
)
```

## Challenge Types

| Type | Description |
|------|-------------|
| `JS_POW` | JavaScript Proof of Work |
| `COOKIE` | Cookie-based challenge |
| `CAPTCHA` | Visual CAPTCHA |
| `CANARY` | Invisible canary page |

## Session Parameters

Each session gets:

- `rate_limit_multiplier` -- Random multiplier for rate limit
- `challenge_type` -- Random challenge type
- `pow_difficulty` -- Random PoW difficulty
- `jitter_ms` -- Random response jitter

## Statistics

```python
stats = randomizer.get_stats()
# {
#     "active_sessions": 50000,
#     "max_sessions": 100000,
#     "rate_limit_range": (80, 120),
#     "challenge_types": ["js_pow", "cookie"],
#     "pow_difficulty_range": (18, 24),
#     "jitter_range": (0, 200),
# }
```
