# DDoS Detection

## How it works

1. Track request counts per client in time buckets
2. Calculate mean and standard deviation of request rates
3. Compute Z-score for each client's current rate
4. Flag clients whose Z-score exceeds the threshold

## Enable

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    ddos_enabled=True,
    ddos_z_score_threshold=3.0,
    ddos_min_samples=100,
    ddos_window=60.0,
)
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `ddos_enabled` | `False` | Enable DDoS detection |
| `ddos_z_score_threshold` | `3.0` | Z-score threshold |
| `ddos_min_samples` | `100` | Min samples before detection |
| `ddos_window` | `60.0` | Sliding window (seconds) |

## Standalone usage

```python
from drogue.protection.ddos import DDoSDetector

detector = DDoSDetector(window=60.0, z_threshold=3.0, min_samples=100)

detector.record("192.168.1.1")
if detector.is_anomalous("192.168.1.1"):
    print("Possible DDoS")

stats = detector.get_stats()
```

## WebSocket support

```python
detector.record_ws("client_abc")
if detector.is_ws_anomalous("client_abc"):
    print("WS flooding")
```

## Tuning

- **Lower threshold (2.0):** More sensitive, more false positives
- **Higher threshold (4.0):** Less sensitive, fewer false positives
- **Smaller window (30s):** Reacts faster, more noise
- **Larger window (120s):** Smoother detection, slower reaction
