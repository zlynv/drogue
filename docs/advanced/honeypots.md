# Honeypots

## What are honeypots?

Honeypots are invisible trap endpoints that only automated bots reach. Real users never see them because they're hidden in HTML (display:none), not linked, or buried in robots.txt. Any client that requests a honeypot path is instantly classified as a bot and auto-banned.

**Why use them?**
- Zero false positives -- legitimate users never trigger honeypots
- Instant bot classification -- no need to analyze behavior patterns
- Auto-banning -- bots are blocked immediately without manual intervention
- Attack intelligence -- collect data on scanning tools and patterns

## How it works

```
1. You register honeypot paths (e.g., /admin/backup.sql, /.env)
2. These paths are invisible to real users (hidden in HTML)
3. Bots crawl your site and hit the honeypots
4. drogue detects the hit and records it
5. The client is flagged as a bot
6. Auto-ban is applied (configurable duration)
7. All subsequent traffic from that client is blocked
```

## Usage

```python
from drogue.defense.randomizer import HoneypotManager

manager = HoneypotManager()

# Register honeypot paths
manager.register("/admin/backup.sql", auto_ban=True, ban_duration=86400.0, response_code=404)
manager.register("/.env", auto_ban=True)
manager.register("/wp-admin", auto_ban=True)

# Check if a path is a honeypot
if manager.is_honeypot("/admin/backup.sql"):
    # Record the hit
    result = manager.record_hit("/admin/backup.sql", "scanner_client_id")
    # result = {'auto_ban': True, 'ban_duration': 86400.0, 'response_code': 404}
```

## Registration options

```python
manager.register(
    path="/admin/backup.sql",     # The trap path
    auto_ban=True,                # Auto-ban on hit
    ban_duration=86400.0,         # Ban duration in seconds (24 hours)
    response_code=404,            # HTTP response code to return
)
```

## Record hit response

When a bot hits a honeypot, `record_hit()` returns:

```python
{
    "auto_ban": True,           # Whether to auto-ban the client
    "ban_duration": 86400.0,    # How long to ban (seconds)
    "response_code": 404        # Response code to send
}
```

Or `None` if the path is not a honeypot.

## Check if client is a bot

```python
# After recording hits, check if client is flagged
is_bot = manager.is_bot("scanner_client_id")  # True

# Get hit history for a client
hits = manager.get_hits("scanner_client_id")  # [1690000000.0, 1690000001.0]

# Get stats
stats = manager.get_stats()
# {
#     "registered_honeypots": 3,
#     "clients_botted": 25,
#     "total_hits": 150,
# }

# Clear a client's bot status
manager.clear_client("scanner_client_id")
```

## Honeypot placement strategies

### Hidden links in HTML

```html
<!-- Invisible to real users, visible to bots -->
<a href="/admin/backup.sql" style="display: none">Click here</a>
<a href="/.env" style="visibility: hidden">Config</a>
```

### Hidden form fields

```html
<!-- Bots auto-fill hidden fields -->
<input type="text" name="website" style="position: absolute; left: -9999px;">
<input type="email" name="email" style="display: none">
```

### robots.txt traps

```
# robots.txt -- honest bots avoid these, malicious bots ignore them
User-agent: *
Disallow: /admin/backup.sql
Disallow: /.env
Disallow: /wp-admin
```

### Zero-size iframes

```html
<!-- Invisible iframe that only bots request -->
<iframe src="/honeypot/monitoring" width="0" height="0" style="display: none"></iframe>
```

### CSS background images

```css
/* Hidden background image that bots download */
.honeypot {
    background-image: url("/honeypot/tracker.gif");
    width: 0;
    height: 0;
}
```

## Integration with Django

```python
# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drogue.defense.randomizer import HoneypotManager

honeypots = HoneypotManager()
honeypots.register("/admin/backup.sql", auto_ban=True)
honeypots.register("/.env", auto_ban=True)

@csrf_exempt
def my_view(request):
    path = request.path

    # Check honeypot
    if honeypots.is_honeypot(path):
        result = honeypots.record_hit(path, request.META.get("REMOTE_ADDR", "unknown"))
        if result and result["auto_ban"]:
            # Apply ban here
            pass
        return JsonResponse({"error": "Not found"}, status=404)

    # Normal request handling
    return JsonResponse({"message": "OK"})
```

## Example: Full bot detection flow

```python
from drogue.defense.randomizer import HoneypotManager
from drogue.protection.ban import ProgressiveBanManager

# Setup
honeypots = HoneypotManager()
ban_manager = ProgressiveBanManager(threshold=1)

# Register traps
honeypots.register("/admin/debug", auto_ban=True)
honeypots.register("/.env", auto_ban=True)

# Bot crawls your site
client_ip = "185.220.101.50"

# Bot hits honeypot
if honeypots.is_honeypot("/admin/debug"):
    result = honeypots.record_hit("/admin/debug", client_ip)
    if result and result["auto_ban"]:
        ban_manager.record_violation(client_ip)

# Check if banned
is_banned = ban_manager.is_banned(client_ip)  # True
```
