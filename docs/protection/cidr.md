# CIDR Filtering

## Usage

```python
from drogue.protection.cidr import CIDRFilter

filter = CIDRFilter()

# Add rules
filter.add("192.168.0.0/16", "allow")
filter.add("10.0.0.0/8", "allow")
filter.add("185.220.101.0/24", "block")
filter.add("2001:db8::/32", "allow")

# Check
action = filter.evaluate("192.168.1.100")  # "allow"
action = filter.evaluate("8.8.8.8")         # None (no match)
```

## Load from file

**blocked_ips.txt:**

```
185.220.101.0/24
2001:db8::/32
```

```python
filter.load_from_file("blocked_ips.txt", "block")
```

## Load from YAML

```yaml
cidr_rules:
  - range: "192.168.0.0/16"
    action: "allow"
  - range: "185.220.101.0/24"
    action: "block"
```

```python
filter.load_from_yaml("cidr_config.yaml")
```

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    cidr_enabled=True,
    cidr_rules_file="cidr_config.yaml",
)
```

## Statistics

```python
stats = filter.get_stats()
# {"ranges": 4, "ipv4": 3, "ipv6": 1, "allows": 3, "blocks": 1}
```
