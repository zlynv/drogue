# Progressive Auto-Ban

## How it works

1. Each violation increments a counter for the client
2. Ban duration doubles with each escalation (5 min, 10 min, 20 min, ..., 160 min max)
3. After `ban_max_level` violations, client is banned for `ban_max_duration`
4. State resets if `ban_reset_window` elapses without violations

## Enable

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    ban_enabled=True,
    ban_initial_duration=300.0,      # 5 minutes
    ban_max_duration=9600.0,         # 160 minutes
    ban_max_level=6,
    ban_reset_window=3600.0,         # 1 hour
)
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `ban_enabled` | `False` | Enable auto-ban |
| `ban_initial_duration` | `300.0` | First ban duration (seconds) |
| `ban_max_duration` | `9600.0` | Maximum ban duration |
| `ban_max_level` | `6` | Maximum escalation level |
| `ban_reset_window` | `3600.0` | Time without violations to reset level |

## Ban state

```python
from drogue.protection.ban import BanManager

manager = BanManager(config)

# Check if banned
if manager.is_banned("192.168.1.1"):
    print("Client is banned")

# Record violation
manager.record_violation("192.168.1.1")

# Get ban info
info = manager.get_ban_info("192.168.1.1")
# {"banned": True, "until": 1690000000.0, "level": 2, "duration": 1200.0}
```

## Ban duration progression

| Level | Duration |
|-------|----------|
| 1 | 5 min |
| 2 | 10 min |
| 3 | 20 min |
| 4 | 40 min |
| 5 | 80 min |
| 6 | 160 min |
