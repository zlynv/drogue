# Defense Randomization

## Per-session randomization

Each client session gets different rate limit values:

```python
from drogue.defense.randomizer import DefenseRandomizer

randomizer = DefenseRandomizer(variance=0.1)

# Get randomized limit
base = 100
randomized = randomizer.randomize_limit(base)  # 90-110
```

## Honeypots

```python
from drogue.defense.randomizer import HoneypotManager

manager = HoneypotManager()

# Get honeypot paths for a session
honey_paths = manager.get_honeypot_paths("session_abc", count=2)
# ["/admin/debug", "/.env"]

# Check if a path is a honeypot
if manager.is_honeypot("/admin/debug"):
    print("Honeypot triggered")

# Get stats
stats = manager.get_stats("session_abc")
# {"requests": 5, "honeypot_hits": 1}
```

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    randomizer_enabled=True,
    randomizer_variance=0.1,
    randomizer_honeypot_count=3,
)
```

## Why randomization helps

- Prevents attackers from discovering exact limits
- Different clients hit limits at different times
- Honeypots detect automated scanners
- Makes reverse-engineering rate limits harder
