# Probe Detection

## Patterns detected

| Pattern | Description |
|---------|-------------|
| Sequential paths | Crawling `/page1`, `/page2`, `/page3` |
| Timing regularity | Requests at fixed intervals |
| User-agent diversity | Rotating user agents |

## Enable

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    probes_enabled=True,
    probes_path_threshold=10,     # paths to detect sequential pattern
    probes_timing_threshold=0.1,  # timing regularity threshold
)
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `probes_enabled` | `False` | Enable probe detection |
| `probes_path_threshold` | `10` | Paths to trigger sequential pattern |
| `probes_timing_threshold` | `0.1` | Timing regularity threshold (0-1) |
| `probes_window` | `300.0` | Observation window (seconds) |

## Standalone usage

```python
from drogue.protection.probes import ProbeDetector

detector = ProbeDetector(window=300.0, path_threshold=10, timing_threshold=0.1)

# Record requests
detector.record("192.168.1.1", "/page1", "Mozilla/5.0")
detector.record("192.168.1.1", "/page2", "Mozilla/5.0")

# Check
if detector.is_probe("192.168.1.1"):
    print("Probe detected")

# Score
score = detector.get_probe_score("192.168.1.1")  # 0.0 to 1.0

# Clear
detector.clear("192.168.1.1")
```
