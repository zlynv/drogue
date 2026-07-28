# Progressive Auto-Ban

## How it works

1. Each violation increments a counter for the client
2. Ban duration escalates with each level (60s, 5min, 15min, 1h, 2h, 4h)
3. After `threshold` violations within the window, client is banned
4. Violations expire after the window elapses

## Usage

```python
from drogue.protection.ban import ProgressiveBanManager

manager = ProgressiveBanManager(
    threshold=5,           # violations before ban
    window=300.0,          # violation window (seconds)
    max_violations=20,
    escalation=[60, 300, 900, 3600, 7200, 14400],
)

# Record a violation
count = manager.record_violation("192.168.1.1")

# Check ban status
is_banned = manager.is_banned("192.168.1.1")

# Get ban details
ban = manager.get_ban("192.168.1.1")
# BanEntry(key='192.168.1.1', level=1, banned_at=..., expires_at=..., violation_count=5)

level = manager.get_ban_level("192.168.1.1")
retry_after = manager.get_retry_after("192.168.1.1")

# Clear
manager.clear_ban("192.168.1.1")
manager.clear_all()
```

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    ban_enabled=True,
    ban_threshold=5,
    ban_window=300.0,
    ban_escalation=[60, 300, 900, 3600, 7200, 14400],
)
```

## Ban duration progression

| Level | Duration |
|-------|----------|
| 1 | 1 min |
| 2 | 5 min |
| 3 | 15 min |
| 4 | 1 hour |
| 5 | 2 hours |
| 6 | 4 hours |
