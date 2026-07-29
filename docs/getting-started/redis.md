# Redis Backend

## Installation

```bash
pip install drogue[redis]
```

## Basic Usage

```python
from drogue.core.storage.redis import RedisStorage
from drogue.adapters.fastapi import DrogueLimiter

storage = RedisStorage(url="redis://localhost:6379")
limiter = DrogueLimiter(app, storage=storage)
```

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    storage_backend="redis",
    redis_url="redis://localhost:6379",
)
```

## Redis URL Format

```python
# Local Redis
RedisStorage(url="redis://localhost:6379")

# Remote Redis
RedisStorage(url="redis://your-redis-host:6379")

# Redis with password
RedisStorage(url="redis://:password@localhost:6379")

# Redis with database
RedisStorage(url="redis://localhost:6379/0")
```

## Connection Pooling

```python
from drogue.core.storage.redis import RedisStorage

storage = RedisStorage(
    url="redis://localhost:6379",
    max_connections=20,
)
```

## Distributed Rate Limiting

Redis enables rate limiting across multiple workers:

```python
from drogue.core.storage.redis import RedisStorage
from drogue.adapters.fastapi import DrogueLimiter

# All workers share the same Redis backend
storage = RedisStorage(url="redis://localhost:6379")

# Each worker creates its own limiter with shared storage
limiter = DrogueLimiter(app, storage=storage)
```

## Performance

| Backend | Latency | Throughput | Use Case |
|---------|---------|------------|----------|
| Memory | ~5 microseconds | 741K req/s | Single worker |
| Redis | ~1ms | 50K req/s | Multi-worker |

## Failover

RedisStorage handles connection failures gracefully:

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    storage_backend="redis",
    redis_url="redis://localhost:6379",
    default_fail_closed=True,  # Deny on Redis failure
)
```
