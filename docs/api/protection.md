# Protection API Reference

## ProgressiveBanManager

```python
from drogue.protection.ban import ProgressiveBanManager

ban = ProgressiveBanManager(
    escalation=[0, 60, 600, 3600, 86400],  # 0s, 1m, 10m, 1hr, 24hr
    threshold=5,                             # Violations before ban
    window=300.0,                            # Violation window (seconds)
    max_violations=10,                       # Max violations before permanent ban
)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `record_violation(key)` | Record violation, auto-ban if threshold exceeded |
| `is_banned(key)` | Check if client is banned |
| `get_ban(key)` | Get BanEntry for client |
| `get_retry_after(key)` | Get seconds until ban expires |
| `get_ban_level(key)` | Get current ban escalation level |
| `clear_ban(key)` | Remove ban for client |
| `clear_all()` | Clear all bans |
| `get_active_bans()` | Get all active ban entries |

**BanEntry:**

```python
@dataclass
class BanEntry:
    key: str
    level: int
    banned_at: float
    expires_at: float
    violation_count: int
```

---

## DDoSDetector

```python
from drogue.protection.ddos import DDoSDetector

detector = DDoSDetector(
    window=60.0,           # Sliding window (seconds)
    z_threshold=3.0,       # Z-score threshold
    min_samples=100,       # Minimum samples for Z-score
    bucket_size=1.0,       # Time bucket size (seconds)
    max_clients=100_000,   # Maximum clients to track
)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `record(client_key)` | Record HTTP request |
| `record_ws(client_key)` | Record WebSocket message |
| `is_anomalous(client_key)` | Check if client is anomalous |
| `is_http_anomalous(client_key)` | Check HTTP anomaly only |
| `is_ws_anomalous(client_key)` | Check WebSocket anomaly only |
| `get_client_rate(client_key)` | Get client's current HTTP rate |
| `get_ws_client_rate(client_key)` | Get client's current WS rate |
| `get_global_rate()` | Get global HTTP request rate |
| `get_ws_global_rate()` | Get global WS message rate |
| `get_stats()` | Get detector statistics |

**Stats:**

```python
stats = detector.get_stats()
# {
#     "http_tracked_clients": 5000,
#     "ws_tracked_clients": 1000,
#     "http_global_rate": 15000.0,
#     "ws_global_rate": 5000.0,
#     "http_window": 60.0,
#     "ws_window": 60.0,
#     "z_threshold": 3.0,
# }
```

---

## TrustManager

```python
from drogue.protection.trust import TrustManager

trust = TrustManager(
    max_fingerprints=100_000,
    trusted_ttl=3600.0,                # 1 hour
    standard_ttl=1800.0,               # 30 minutes
    score_threshold_trusted=0.8,       # Score >= 0.8 = TRUSTED
    score_threshold_standard=0.5,      # Score >= 0.5 = STANDARD
)
```

**TrustLevel Enum:**

```python
from drogue.protection.trust import TrustLevel

TrustLevel.UNKNOWN      # Not yet evaluated
TrustLevel.EVALUATED    # Has been evaluated
TrustLevel.TRUSTED      # High trust (skip expensive checks)
TrustLevel.STANDARD     # Normal trust
TrustLevel.SUSPICIOUS   # Low trust
TrustLevel.POISONED     # Poisoned (attacker tried to manipulate)
TrustLevel.BANNED       # Banned
```

**Methods:**

| Method | Description |
|--------|-------------|
| `check(fingerprint)` | Get TrustState for fingerprint |
| `is_trusted(fingerprint)` | Check if fingerprint is TRUSTED |
| `update(fingerprint, score)` | Update trust score |
| `poison(fingerprint)` | Poison fingerprint (attacker detected) |
| `ban(fingerprint)` | Ban fingerprint |
| `is_banned(fingerprint)` | Check if banned |
| `get_state(fingerprint)` | Get TrustState |
| `get_stats()` | Get trust statistics |
| `clear()` | Clear all trust states |

**TrustState:**

```python
@dataclass
class TrustState:
    level: TrustLevel
    created_at: float
    expires_at: float
    score: float
    request_count: int
    anomaly_count: int

    @property
    def expired(self) -> bool: ...

    @property
    def age(self) -> float: ...
```

---

## SentinelDetector

```python
from drogue.protection.sentinel import SentinelDetector, extract_features

detector = SentinelDetector(
    n_features=5,
    n_trees=100,
    window_size=256,
    max_depth=15,
    target_fpr=0.01,       # Target false positive rate
    score_window=1000,     # Samples for threshold calibration
)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `analyze(features)` | Analyze feature vector, return anomaly score |
| `get_threshold()` | Get current anomaly threshold |
| `get_stats()` | Get detector statistics |

**Feature Extraction:**

```python
context = {
    "rate": 50.0,        # Requests per minute
    "path_diversity": 0.3, # Unique paths / total
    "error_ratio": 0.1,   # 4xx+5xx / total
    "hour_sin": 0.5,      # sin(hour / 24 * 2π)
    "hour_cos": 0.866,    # cos(hour / 24 * 2π)
}

features = extract_features(context)
# Returns list of 5 floats

score = detector.analyze(features)
threshold = detector.get_threshold()

if score > threshold:
    # Anomaly detected
    pass
```

---

## ProbeDetector

```python
from drogue.protection.probes import ProbeDetector

detector = ProbeDetector(
    window=300.0,           # Time window (seconds)
    probe_threshold=3,      # Min unique paths for probe
    min_error_rate=0.5,     # Min error rate to flag
    max_time_span=60.0,     # Max time span for probe
    threat_boost=0.3,       # Threat score boost
    max_clients=10_000,     # Max clients to track
    cleanup_interval=60.0,  # Cleanup interval (seconds)
)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `record(client_id, path, status_code, method, timestamp)` | Record request |
| `is_probing(client_id)` | Check if client is probing |
| `get_threat_boost(client_id)` | Get threat score boost |
| `get_signal(client_id)` | Get ProbeSignal |
| `get_stats()` | Get detector statistics |
| `clear_client(client_id)` | Clear client data |
| `clear_all()` | Clear all data |

**ProbeSignal:**

```python
@dataclass
class ProbeSignal:
    client_id: str
    unique_paths: int
    error_count: int
    total_count: int
    time_span: float
    threat_boost: float
    detected_at: float
```

---

## CIDRFilter

```python
from drogue.protection.cidr import CIDRFilter

filter = CIDRFilter(
    allowlist=["10.0.0.0/8"],
    denylist=["192.168.1.100/32"],
)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `is_denied(ip)` | Check if IP is denied |
| `is_allowed(ip)` | Check if IP is allowed |
| `add_to_denylist(cidr)` | Add CIDR to denylist |
| `add_to_allowlist(cidr)` | Add CIDR to allowlist |
| `remove_from_denylist(cidr)` | Remove CIDR from denylist |
| `remove_from_allowlist(cidr)` | Remove CIDR from allowlist |
| `load_from_file(path, list_type)` | Load CIDRs from file |
| `get_stats()` | Get filter statistics |

**File Format:**

```
# Comments start with #
192.168.1.100/32
10.0.0.0/8
172.16.0.0/12
```

---

## AdaptiveRateLimiter

```python
from drogue.protection.adaptive import AdaptiveRateLimiter

adaptive = AdaptiveRateLimiter(
    cpu_threshold=0.8,       # Reduce when CPU > 80%
    memory_threshold=0.8,    # Reduce when memory > 80%
    latency_threshold=1.0,   # Reduce when p95 > 1s
    check_interval=5.0,      # Check every 5 seconds
)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `get_effective_limit(base_limit)` | Get adjusted limit |
| `record_latency(latency)` | Record request latency |
| `get_metrics()` | Get system metrics |

**Dependencies:**

```bash
pip install drogue[adaptive]
```
