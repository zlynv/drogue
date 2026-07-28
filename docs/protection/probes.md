# Probe Detection

## Patterns detected

| Pattern | Description |
|---------|-------------|
| Sequential paths | Crawling `/page1`, `/page2`, `/page3` |
| High error rate | Many 4xx/5xx responses |
| Timing regularity | Requests at fixed intervals |

## Usage

```python
from drogue.protection.probes import ProbeDetector

detector = ProbeDetector(
    window=300.0,           # observation window (seconds)
    probe_threshold=3,      # paths to trigger detection
    min_error_rate=0.5,     # minimum error rate threshold
    max_time_span=60.0,     # max time for sequential pattern
    threat_boost=0.3,       # threat score boost per probe
    max_clients=10000,
)

# Record requests
detector.record("scanner.ip", "/page1", status_code=200, method="GET")
detector.record("scanner.ip", "/page2", status_code=200, method="GET")
detector.record("scanner.ip", "/admin", status_code=403, method="GET")

# Check if client is probing
is_probing = detector.is_probing("scanner.ip")

# Get signal details
signal = detector.get_signal("scanner.ip")

# Threat boost (0.0 to 1.0)
boost = detector.get_threat_boost("scanner.ip")

# Cleanup
detector.clear_client("scanner.ip")
detector.clear_all()

# Stats
stats = detector.get_stats()
```
