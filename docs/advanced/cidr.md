# CIDR Filtering

## Overview

CIDR Filtering allows blocking or allowing IP ranges using CIDR notation.

## Usage

```python
from drogue.protection.cidr import CIDRFilter

filter = CIDRFilter(
    allowlist=["10.0.0.0/8"],          # Only allow these
    denylist=["192.168.1.100/32"],      # Always block these
)

if filter.is_denied("192.168.1.100"):
    return 403
```

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    cidr_allowlist=["10.0.0.0/8", "192.168.0.0/16"],
    cidr_denylist=["192.168.1.100/32"],
)
```

## CIDR Notation

| Notation | Description |
|----------|-------------|
| `10.0.0.0/8` | Class A network (16M addresses) |
| `172.16.0.0/12` | Class B network (1M addresses) |
| `192.168.0.0/16` | Class C network (65K addresses) |
| `192.168.1.100/32` | Single host |

## File Loading

```python
from drogue.protection.cidr import CIDRFilter

filter = CIDRFilter()
filter.load_from_file("blocked_ips.txt", list_type="denylist")
```

**File format:**

```
# Comments start with #
192.168.1.100/32
10.0.0.0/8
172.16.0.0/12
```

## Dynamic Updates

```python
# Add at runtime
filter.add_to_denylist("203.0.113.0/24")
filter.add_to_allowlist("10.0.0.0/8")

# Remove at runtime
filter.remove_from_denylist("203.0.113.0/24")
```

## Integration with drogue

```python
class DrogueLimiter:
    async def _check(self, context):
        # Check CIDR filter
        if self._cidr_filter and context:
            client_ip = context.get("client", {}).get("host", "")
            if client_ip and self._cidr_filter.is_denied(client_ip):
                # Deny immediately
                return AcquireResult(
                    allowed=False,
                    limit=rule.limit,
                    remaining=0,
                    retry_after=0,
                    headers={},
                )

        # Continue with rate limit check
        ...
```

## Statistics

```python
stats = filter.get_stats()
# {
#     "allowlist_count": 2,
#     "denylist_count": 1,
#     "allowlist": ["10.0.0.0/8", "192.168.0.0/16"],
#     "denylist": ["192.168.1.100/32"],
# }
```

## Use Cases

- **Geographic blocking:** Block countries by IP range
- **VPN blocking:** Block known VPN provider ranges
- **Whitelisting:** Only allow internal network ranges
- **Temporary bans:** Ban specific IP ranges during attacks
