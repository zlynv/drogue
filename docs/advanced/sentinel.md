# Sentinel Model

## Overview

The Sentinel Model implements Half-Space Trees for streaming anomaly detection that catches zero-day attacks.

## Properties

- Single-pass: O(1) per data point
- Bounded memory: ~5MB fixed-size sketch
- No labels needed: learns "normal" from recent traffic
- Concept drift aware: adapts to time-of-day patterns
- Self-calibrating: maintains target 0.1% false positive rate

## Usage

```python
from drogue.protection.sentinel import SentinelDetector

sentinel = SentinelDetector(
    n_features=5,
    n_trees=25,
    window_size=256,
    max_depth=15,
    target_fpr=0.001,
    score_window=1000,
)

# Extract features
features = [
    context["requests_per_minute"],
    context["unique_endpoints"],
    context["avg_inter_arrival_ms"],
    context["error_rate"],
    context["bytes_per_request"],
]

# Score and update
is_anomaly = sentinel.analyze(features)

# Get adaptive threshold
threshold = sentinel.get_threshold()
```

## Features

The Sentinel Model uses these features for anomaly detection:

| Feature | Description |
|---------|-------------|
| `requests_per_minute` | Request rate per fingerprint |
| `unique_endpoints` | Endpoint diversity |
| `avg_inter_arrival_ms` | Timing pattern between requests |
| `error_rate` | 4xx/5xx response ratio |
| `bytes_per_request` | Payload size pattern |

## How Half-Space Trees Work

1. Build a forest of isolation trees
2. Each tree randomly splits features
3. Anomalous points are isolated quickly (short path)
4. Normal points require deep traversal (long path)
5. Score is negative average depth (higher = more anomalous)

## Integration with drogue

Sentinel runs inside the pipeline on a sample of requests (scoring
every request would dominate CPU at high throughput). By default it
only observes and logs; set `sentinel_block=True` to deny anomalies
with a 429.

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    sentinel_enabled=True,
    sentinel_sample_rate=0.01,  # score 1% of requests
    sentinel_block=False,       # True to deny anomalies
)
limiter = DrogueLimiter(FastAPI(), config=config)  # auto-builds pipeline
```

Manual wiring through your own pipeline, with custom features:

```python
from drogue.protection import ProtectionPipeline, SentinelDetector
from drogue.protection import extract_features

sentinel = SentinelDetector(n_features=5, n_trees=25, window_size=256)
pipeline = ProtectionPipeline(
    sentinel=sentinel,
    sentinel_sample_rate=0.05,
    sentinel_block=True,
    feature_fn=extract_features,  # or your own ctx -> [float x5]
)

result = await pipeline.check(key, context)  # 429 sentinel_anomaly if blocked
```

The detector needs a warm-up of a few hundred requests before the
forest exists; until then every request passes. Scores from before
the forest exists are never fed to the adaptive threshold, so
warm-up traffic cannot blind later detection.

## Statistics

```python
stats = sentinel.get_stats()
# {
#     "total_count": 10000,
#     "anomaly_count": 15,
#     "anomaly_rate": 0.0015,
#     "current_threshold": -12.5,
#     "score_window_size": 1000,
#     "feature_importance": [0.3, 0.25, 0.2, 0.15, 0.1],
# }
```

## Comparison with Z-Score

| Aspect | Z-Score | Sentinel |
|--------|---------|----------|
| Adaptation | Static threshold | Self-calibrating |
| Features | Single (request count) | Multiple (5 features) |
| Concept drift | No | Yes |
| Zero-day detection | No | Yes |
| Memory | Low | Medium (~5MB) |
