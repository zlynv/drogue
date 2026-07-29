# Progressive Auto-Ban

## What is auto-ban?

Auto-ban automatically blocks clients that repeatedly violate rate limits. Unlike simple ban lists, progressive auto-ban increases the ban duration with each violation, making it harder for persistent abusers to return.

## How it works

```
1. Client violates rate limit -> violation recorded
2. If violations reach threshold within the window, client is banned
3. Ban duration escalates with each level:
   - Level 1: 1 minute
   - Level 2: 5 minutes
   - Level 3: 15 minutes
   - Level 4: 1 hour
   - Level 5: 2 hours
   - Level 6: 4 hours
4. Violations expire after the window elapses
5. Ban expires after the duration elapses
```

## Usage

```python
from drogue.protection.ban import ProgressiveBanManager

manager = ProgressiveBanManager(
    threshold=5,           # Violations before ban
    window=300.0,          # Violation window (5 minutes)
    max_violations=20,     # Max violations to track
    escalation=[60, 300, 900, 3600, 7200, 14400],  # Duration per level
)

# Record a violation
count = manager.record_violation("192.168.1.1")
# 1 (first violation)

count = manager.record_violation("192.168.1.1")
# 2 (second violation)

# After 5 violations within 300 seconds:
count = manager.record_violation("192.168.1.1")
# 5 (ban triggered!)

# Check ban status
is_banned = manager.is_banned("192.168.1.1")  # True
```

## Response examples

### `record_violation()` response

```python
count = manager.record_violation("192.168.1.1")
# 3  (total violations for this client)
```

### `get_ban()` response

```python
ban = manager.get_ban("192.168.1.1")
# BanEntry(
#     key='192.168.1.1',
#     level=1,                          # Escalation level
#     banned_at=1690000000.0,           # When banned
#     expires_at=1690000060.0,          # When ban expires
#     violation_count=5,                # Total violations
# )

# Or None if not banned
ban = manager.get_ban("10.0.0.1")  # None
```

### `get_retry_after()` response

```python
retry_after = manager.get_retry_after("192.168.1.1")
# 45.2  (seconds until ban expires)
# None  (if not banned)
```

### `get_active_bans()` response

```python
bans = manager.get_active_bans()
# {
#     "192.168.1.1": BanEntry(level=1, ...),
#     "10.0.0.50": BanEntry(level=2, ...),
# }
```

## Clear bans

```python
# Clear ban for a specific client
cleared = manager.clear_ban("192.168.1.1")  # True

# Clear all bans
count = manager.clear_all()  # Returns number of cleared bans
```

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    ban_enabled=True,
    ban_threshold=5,           # Violations before ban
    ban_window=300.0,          # Violation window (seconds)
    ban_escalation=[60, 300, 900, 3600, 7200, 14400],
)
```
