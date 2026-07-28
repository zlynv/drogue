# Honeypots

## Overview

Honeypots are invisible trap endpoints that only bots reach. Any client that hits a honeypot is instantly classified as a bot and auto-banned.

## Usage

```python
from drogue.defense.randomizer import HoneypotManager

honeypots = HoneypotManager()

# Register honeypot paths
honeypots.register("/admin/backup.sql", auto_ban=True)
honeypots.register("/honeypot/hidden-link", auto_ban=True)

# Check if request hit a honeypot
if honeypots.is_honeypot("/admin/backup.sql"):
    config = honeypots.record_hit("/admin/backup.sql", client_id)
    if config["auto_ban"]:
        ban_manager.record_violation(client_id)
```

## Registration

```python
honeypots.register(
    path="/admin/backup.sql",
    auto_ban=True,           # Auto-ban on hit
    ban_duration=86400.0,    # 24 hours
    response_code=404,       # Return 404
)
```

## How It Works

1. Register honeypot paths
2. Honeypots are invisible to real users (hidden in HTML, not linked)
3. Bots that crawl the site hit honeypots
4. Client is instantly classified as bot
5. Auto-ban is applied
6. All traffic from that client is re-evaluated

## Honeypot Types

### Hidden Links

```html
<!-- Invisible to real users, visible to bots -->
<a href="/honeypot/hidden-link" style="display: none">Click here</a>
```

### Hidden Form Fields

```html
<!-- Bots auto-fill hidden fields -->
<input type="text" name="website" style="position: absolute; left: -9999px;">
```

### robots.txt Traps

```
# robots.txt
User-agent: *
Disallow: /honeypot/
Disallow: /admin/backup.sql
```

### Zero-Size Iframes

```html
<!-- Invisible iframe that only bots request -->
<iframe src="/honeypot/monitoring" width="0" height="0" style="display: none"></iframe>
```

## Integration with drogue

```python
class DrogueLimiter:
    async def _check(self, context):
        # Check if request hit a honeypot
        if self._honeypot_manager and context:
            path = context.get("path", "")
            if self._honeypot_manager.is_honeypot(path):
                config = self._honeypot_manager.record_hit(path, key)
                if config and config["auto_ban"]:
                    await self._ban_manager.record_violation(key)

        # Continue with rate limit check
        ...
```

## Statistics

```python
stats = honeypots.get_stats()
# {
#     "registered_honeypots": 5,
#     "clients_botted": 25,
#     "total_hits": 150,
# }
```

## Use Cases

- **Bot detection:** Instantly classify automated traffic
- **Zero false positives:** Legitimate users never see honeypots
- **Auto-banning:** Ban bots without manual intervention
- **Threat intelligence:** Collect data on attack patterns
