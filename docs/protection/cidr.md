# CIDR Filtering

## What is CIDR filtering?

CIDR (Classless Inter-Domain Routing) filtering allows you to block or allow entire IP ranges. Instead of blocking one IP at a time, you can block a subnet like `185.220.101.0/24` (256 IPs) with a single rule.

## Why it matters

- Block known malicious IP ranges (VPN providers, hosting providers used for attacks)
- Allow internal networks (10.0.0.0/8, 192.168.0.0/16)
- Prevent geographic-based attacks
- Reduce load by blocking traffic at the application level

## How CIDR notation works

```
192.168.1.0/24
│              │
│              └── /24 = first 24 bits are the network
│                       Last 8 bits are host IPs
│                       = 256 IPs (192.168.1.0 - 192.168.1.255)
│
└── Network address

10.0.0.0/8
│         │
│         └── /8 = first 8 bits are the network
│                  = 16.7 million IPs (10.0.0.0 - 10.255.255.255)
│
└── Network address
```

## Usage

```python
from drogue.protection.cidr import CIDRFilter

cidr = CIDRFilter()

# Add to allowlist (always pass)
cidr.add_to_allowlist("192.168.0.0/16")    # Private network
cidr.add_to_allowlist("10.0.0.0/8")        # Internal IPs
cidr.add_to_allowlist("172.16.0.0/12")     # Docker networks

# Add to denylist (always block)
cidr.add_to_denylist("185.220.101.0/24")   # Known scanner range
cidr.add_to_denylist("2001:db8::/32")      # IPv6 range

# Check an IP
is_allowed = cidr.is_allowed("192.168.1.100")  # True (in allowlist)
is_denied = cidr.is_denied("185.220.101.50")   # True (in denylist)
is_allowed = cidr.is_allowed("8.8.8.8")        # False (not in allowlist)
is_denied = cidr.is_denied("8.8.8.8")          # False (not in denylist)
```

## Response examples

### `get_stats()` response

```python
stats = cidr.get_stats()
# {
#     "allowlist_count": 3,        # Number of allowlist rules
#     "denylist_count": 2,         # Number of denylist rules
#     "allowlist": [               # Allowlist ranges
#         "192.168.0.0/16",
#         "10.0.0.0/8",
#         "172.16.0.0/12",
#     ],
#     "denylist": [                # Denylist ranges
#         "185.220.101.0/24",
#         "2001:db8::/32",
#     ],
# }
```

## Load from file

```python
# blocked_ips.txt (one CIDR per line)
# 185.220.101.0/24
# 2001:db8::/32

count = cidr.load_from_file("blocked_ips.txt", list_type="denylist")
# 2 (loaded 2 rules)
```

## Remove rules

```python
cidr.remove_from_allowlist("192.168.0.0/16")
cidr.remove_from_denylist("185.220.101.0/24")
```

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    cidr_allowlist=["192.168.0.0/16", "10.0.0.0/8"],
    cidr_denylist=["185.220.101.0/24"],
)
```
