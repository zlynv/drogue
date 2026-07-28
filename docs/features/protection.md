# Protection Layer

## Overview

drogue provides multiple protection mechanisms beyond basic rate limiting.

## DDoS Detection

Z-score anomaly detection for HTTP and WebSocket traffic.

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    ddos_enabled=True,
    ddos_z_score_threshold=3.0,
    ddos_min_samples=100,
    ddos_window=60.0,
)
```

## Sentinel Model

Streaming anomaly detection for zero-day attacks.

```python
from drogue.protection.sentinel import SentinelDetector

sentinel = SentinelDetector(
    n_features=5,
    n_trees=25,
    window_size=256,
    target_fpr=0.001,
)
```

See [Sentinel Model](../advanced/sentinel.md) for details.

## Probe Detection

Early attack detection before the flood.

```python
from drogue.protection.probes import ProbeDetector

detector = ProbeDetector(
    window=300.0,
    probe_threshold=3,
    min_error_rate=0.5,
    threat_boost=0.3,
)
```

See [Probe Detection](../advanced/probes.md) for details.

## Progressive Auto-Ban

Escalating bans for repeated violations.

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    ban_enabled=True,
    ban_threshold=5,
    ban_window=300.0,
    ban_escalation=[0, 60, 600, 3600, 86400],  # 0s, 1min, 10min, 1hr, 24hr
)
```

**Ban levels:**

| Level | Duration | Trigger |
|-------|----------|---------|
| 0 | Warning | Below threshold |
| 1 | 1 minute | 5 violations |
| 2 | 10 minutes | 7 violations |
| 3 | 1 hour | 9 violations |
| 4 | 24 hours | 11+ violations |

## Circuit Breaker

Protects backend from cascading failures.

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    circuit_breaker_enabled=True,
    circuit_failure_threshold=5,
    circuit_recovery_timeout=30.0,
    circuit_jitter=0.2,
)
```

**States:**

- CLOSED -- Normal operation, requests pass through
- OPEN -- Backend failing, all requests rejected
- HALF_OPEN -- Testing recovery, some requests pass through

## CIDR Filtering

Block or allow IP ranges.

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    cidr_allowlist=["10.0.0.0/8"],
    cidr_denylist=["192.168.1.100/32"],
)
```

See [CIDR Filtering](../advanced/cidr.md) for details.

## Adaptive Rate Limiting

System-aware throttling based on CPU, memory, and latency.

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    adaptive_enabled=True,
    adaptive_cpu_threshold=0.8,
    adaptive_memory_threshold=0.8,
    adaptive_latency_threshold=1.0,
)
```

See [Adaptive Limits](../advanced/adaptive.md) for details.

## Shadow Mode

Evaluate rules without enforcing.

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(shadow_enabled=True)
```

See [Shadow Mode](../advanced/shadow.md) for details.

## Trust Caching

Tiered processing for trusted users.

See [Trust State Machine](../advanced/trust.md) for details.

## Defense Randomization

Per-session randomized limits.

See [Defense Randomization](../advanced/randomizer.md) for details.

## Honeypots

Auto-ban on trap endpoints.

See [Honeypots](../advanced/honeypots.md) for details.
