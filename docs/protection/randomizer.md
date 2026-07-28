# Defense Randomization

## Per-session randomization

Each client session gets different rate limit values:

```python
from drogue.defense.randomizer import DefenseRandomizer

randomizer = DefenseRandomizer(
    rate_limit_range=(80, 120),  # randomize between 80-120% of base
)

# Get randomized limit for a session
effective = randomizer.get_effective_limit("session_abc", base_limit=100)
# 80 to 120 depending on session
```

## Honeypots

```python
from drogue.defense.randomizer import HoneypotManager

manager = HoneypotManager()

# Register honeypot paths
manager.register("/admin/debug", auto_ban=True, ban_duration=3600.0, response_code=404)
manager.register("/.env", auto_ban=True)
manager.register("/wp-admin", auto_ban=True)

# Check if a path is a honeypot
if manager.is_honeypot("/admin/debug"):
    print("Honeypot triggered")

# Record a hit
manager.record_hit("/admin/debug", "scanner_client_id")

# Check if client is a bot
if manager.is_bot("scanner_client_id"):
    print("Bot detected")

# Get hit history for a client
hits = manager.get_hits("scanner_client_id")  # list of timestamps

# Get stats
stats = manager.get_stats()
# {"registered_honeypots": 3, "clients_botted": 2, "total_hits": 5}

# Clear a client
manager.clear_client("scanner_client_id")
```

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    adaptive_enabled=True,
    adaptive_cpu_threshold=0.8,
    adaptive_memory_threshold=0.8,
)
```

## Why randomization helps

- Prevents attackers from discovering exact limits
- Different clients hit limits at different times
- Honeypots detect automated scanners
- Makes reverse-engineering rate limits harder
