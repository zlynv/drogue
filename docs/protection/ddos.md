# DDoS Detection

## How it works

1. Track request counts per client in time buckets
2. Calculate mean and standard deviation of request rates
3. Compute Z-score for each client's current rate
4. Flag clients whose Z-score exceeds the threshold

## Usage

```python
from drogue.protection.ddos import DDoSDetector

detector = DDoSDetector(
    window=60.0,            # sliding window (seconds)
    z_threshold=3.0,        # Z-score threshold
    min_samples=100,        # min samples before detection
    bucket_size=1.0,        # time bucket size (seconds)
    max_clients=10000,
)

# Record HTTP traffic
detector.record("192.168.1.1")

# Record WebSocket traffic
detector.record_ws("client_abc")

# Check anomalies
is_anomalous = detector.is_anomalous("192.168.1.1")
is_http = detector.is_http_anomalous("192.168.1.1")
is_ws = detector.is_ws_anomalous("client_abc")

# Get rates
rate = detector.get_client_rate("192.168.1.1")
global_rate = detector.get_global_rate()
ws_rate = detector.get_ws_client_rate("client_abc")
ws_global = detector.get_ws_global_rate()

# Stats
stats = detector.get_stats()
# {"http_clients": 150, "ws_clients": 10, "http_global_rate": 500.0, ...}
```

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    ddos_enabled=True,
    ddos_z_score_threshold=3.0,
    ddos_min_samples=100,
    ddos_window=60.0,
)
```

## Tuning

- **Lower threshold (2.0):** More sensitive, more false positives
- **Higher threshold (4.0):** Less sensitive, fewer false positives
- **Smaller window (30s):** Reacts faster, more noise
- **Larger window (120s):** Smoother detection, slower reaction
