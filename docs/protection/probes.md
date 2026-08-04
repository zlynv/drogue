# Probe Detection

## What is probe detection?

Probe detection identifies bots and scanners by analyzing their behavior patterns. Bots typically crawl websites in predictable ways: sequential paths, fixed timing, high error rates. drogue detects these patterns and flags clients as probes.

## What patterns are detected

| Pattern | Description | Example |
|---------|-------------|---------|
| Sequential paths | Crawling /page1, /page2, /page3 | Bot scanning your site |
| High error rate | Many 4xx/5xx responses | Bot hitting non-existent pages |
| Timing regularity | Requests at fixed intervals | Automated script |

## How it works

```
1. Track each client's request history (path, status code, timing)
2. Analyze for probe signals:
   - Are paths sequential? (e.g., /page1, /page2, /page3)
   - Is the error rate high? (many 404s, 403s)
   - Is timing too regular? (exactly 1 request/second)
3. If signals exceed threshold, client is flagged as probing
4. Threat boost is calculated (0.0 to 1.0)
```

## Usage

```python
from drogue.protection.probes import ProbeDetector

detector = ProbeDetector(
    window=300.0,           # Observation window (5 minutes)
    probe_threshold=3,      # Signals needed to flag as probe
    min_error_rate=0.5,     # Minimum error rate to trigger
    max_time_span=60.0,     # Max time for sequential pattern
    threat_boost=0.3,       # Threat score boost per probe signal
    max_clients=10000,
)

# Record requests (called on each request)
detector.record(
    client_id="scanner.ip",
    path="/page1",
    status_code=200,
    method="GET",
)

detector.record("scanner.ip", "/page2", 200, "GET")
detector.record("scanner.ip", "/page3", 404, "GET")  # 404 adds to probe signal

# Check if client is probing
is_probing = detector.is_probing("scanner.ip")  # True or False

# Get detailed signal
signal = detector.get_signal("scanner.ip")
# ProbeSignal(
#     client_id='scanner.ip',
#     unique_paths=3,            # Number of unique paths visited
#     high_error_rate=True,      # Detected high errors
#     total_count=3,             # Total requests
#     time_span=10.0,            # Time span of requests
#     threat_boost=0.6,          # Accumulated threat score
#     detected_at=1690000000.0,  # When probe was detected
#     error_count=1,             # Error responses (4xx/5xx)
# )

# Get threat boost (used by trust system)
boost = detector.get_threat_boost("scanner.ip")
# 0.6  (0.3 per signal x 2 signals)
```

## Response examples

### `get_signal()` response

```python
signal = detector.get_signal("scanner.ip")
# ProbeSignal(
#     client_id='scanner.ip',
#     unique_paths=3,            # Number of unique paths visited
#     high_error_rate=True,      # Detected high errors
#     total_count=3,             # Total requests
#     time_span=10.0,            # Time span of requests
#     threat_boost=0.6,          # Accumulated threat score
#     detected_at=1690000000.0,  # When probe was detected
#     error_count=1,             # Error responses (4xx/5xx)
# )

# Or None if no signal detected
signal = detector.get_signal("normal_user")  # None
```

### `get_stats()` response

```python
stats = detector.get_stats()
# {
#     "total_requests": 5000,
#     "probes_detected": 12,
#     "active_probes": 5,
#     "clients_tracked": 150,
# }
```

### `get_threat_boost()` response

```python
boost = detector.get_threat_boost("scanner.ip")
# 0.0  -- no threat detected
# 0.3  -- one probe signal
# 0.6  -- two probe signals
# 1.0  -- maximum threat (all signals triggered)
```

## Cleanup

```python
# Clear a specific client
detector.clear_client("scanner.ip")

# Clear all data
count = detector.clear_all()  # Returns number of cleared clients
```

## Configuration

```python
from drogue.protection.probes import ProbeDetector

detector = ProbeDetector(
    window=300.0,
    probe_threshold=3,
    min_error_rate=0.5,
    max_time_span=60.0,
)
```
