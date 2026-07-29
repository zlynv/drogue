# DDoS Detection

## What is DDoS detection?

DDoS (Distributed Denial of Service) attacks use many clients to overwhelm your service. Traditional rate limiting catches individual abusers, but DDoS attacks spread requests across many IPs, each staying below the limit. drogue's DDoS detector uses statistical analysis to catch these distributed attacks.

## How it works

### Z-Score Analysis

```
1. Track request rates for each client over time
2. Calculate the mean (average) and standard deviation of all client rates
3. For each new request, calculate the Z-score:
   Z = (client_rate - mean_rate) / standard_deviation
4. If Z > threshold (default 3.0), the client is anomalous
```

**What is a Z-score?**

A Z-score tells you how many standard deviations a value is from the mean:
- Z = 0: exactly average
- Z = 1: slightly above average
- Z = 2: notably above average
- Z = 3: significantly above average (anomalous)
- Z = 4+: extremely high (attack)

### Example scenario

```
Your API normally gets:
- 100 clients, each making 10 requests/minute
- Mean rate: 10 req/min
- Standard deviation: 2 req/min

A DDoS attack starts with 50 bots, each making 50 requests/minute:
- Bot rate: 50 req/min
- Z-score: (50 - 10) / 2 = 20.0
- Threshold: 3.0
- Result: All 50 bots are flagged as anomalous
```

## Usage

```python
from drogue.protection.ddos import DDoSDetector

detector = DDoSDetector(
    window=60.0,            # Sliding window (seconds)
    z_threshold=3.0,        # Z-score threshold for anomaly
    min_samples=100,        # Min samples before detection activates
    bucket_size=1.0,        # Time bucket size (seconds)
    max_clients=10000,      # Max clients to track
)

# Record HTTP traffic
detector.record("192.168.1.1")  # Called on every request

# Record WebSocket traffic
detector.record_ws("client_abc")  # Called on every WS message

# Check if client is anomalous
is_anomalous = detector.is_anomalous("192.168.1.1")  # True or False

# Check HTTP-only or WS-only
is_http = detector.is_http_anomalous("192.168.1.1")
is_ws = detector.is_ws_anomalous("client_abc")

# Get client's current rate
rate = detector.get_client_rate("192.168.1.1")  # e.g., 50.0 requests/second

# Get global rate
global_rate = detector.get_global_rate()  # e.g., 500.0 requests/second
```

## Response examples

### `get_stats()` response

```python
stats = detector.get_stats()
# {
#     "http_clients": 150,           # Number of HTTP clients tracked
#     "ws_clients": 10,              # Number of WebSocket clients tracked
#     "http_global_rate": 500.0,     # Global HTTP requests/second
#     "http_mean": 3.33,             # Mean rate per client
#     "http_std": 1.2,               # Standard deviation
#     "ws_global_rate": 50.0,        # Global WS messages/second
#     "ws_mean": 5.0,                # Mean WS rate per client
#     "ws_std": 1.5,                 # WS standard deviation
# }
```

### `get_client_rate()` response

```python
rate = detector.get_client_rate("192.168.1.1")
# 50.0  (requests per second)
```

### `is_anomalous()` response

```python
is_anomalous = detector.is_anomalous("192.168.1.1")
# True  (Z-score > 3.0, client is suspicious)
# False (client is within normal range)
```

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    ddos_enabled=True,
    ddos_z_score_threshold=3.0,   # Lower = more sensitive
    ddos_min_samples=100,         # Min samples before detection
    ddos_window=60.0,             # Sliding window size
)
```

## Tuning guide

| Scenario | Threshold | Window | Effect |
|----------|-----------|--------|--------|
| Strict (banking) | 2.0 | 30s | Catches attacks faster, more false positives |
| Balanced (SaaS) | 3.0 | 60s | Good default |
| Lenient (gaming) | 4.0 | 120s | Fewer false positives, slower detection |
