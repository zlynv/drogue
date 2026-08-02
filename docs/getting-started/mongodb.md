---
description: Use MongoDB as a distributed storage backend for drogue rate limiting.
---

# MongoDB Backend

## Installation

```bash
pip install drogue[mongodb]
```

This installs `motor` (async MongoDB driver).

## Basic Usage

```python
from drogue.core.storage.mongo import MongoDBStorage
from drogue.adapters.fastapi import DrogueLimiter

storage = MongoDBStorage(uri="mongodb://localhost:27017")
limiter = DrogueLimiter(app, storage=storage)
```

## Configuration

```python
from drogue.core.storage.mongo import MongoDBStorage

storage = MongoDBStorage(
    uri="mongodb://localhost:27017",
    database="myapp",
    collection="rate_limits",
)
```

## MongoDB URI Format

```python
# Local MongoDB
MongoDBStorage(uri="mongodb://localhost:27017")

# Remote MongoDB
MongoDBStorage(uri="mongodb://your-mongo-host:27017")

# MongoDB with authentication
MongoDBStorage(uri="mongodb://user:password@localhost:27017")

# MongoDB Atlas
MongoDBStorage(uri="mongodb+srv://user:password@cluster.mongodb.net")

# MongoDB with replica set
MongoDBStorage(uri="mongodb://host1:27017,host2:27017,host3:27017/?replicaSet=myReplicaSet")
```

## Connection Pooling

```python
from drogue.core.storage.mongo import MongoDBStorage

storage = MongoDBStorage(
    uri="mongodb://localhost:27017",
    database="myapp",
)
```

Motor handles connection pooling automatically.

## Distributed Rate Limiting

MongoDB enables rate limiting across multiple workers:

```python
from drogue.core.storage.mongo import MongoDBStorage
from drogue.adapters.fastapi import DrogueLimiter

# All workers share the same MongoDB backend
storage = MongoDBStorage(uri="mongodb://localhost:27017")

# Each worker creates its own limiter with shared storage
limiter = DrogueLimiter(app, storage=storage)
```

## Performance

| Backend | Latency | Throughput | Use Case |
|---------|---------|------------|----------|
| Memory | ~1.4us | 700K req/s | Single worker |
| Redis | ~1ms | 50K req/s | Multi-worker |
| MongoDB | ~2ms | 20K req/s | Existing MongoDB infrastructure |

## Failover

MongoDBStorage handles connection failures gracefully:

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    default_fail_closed=True,  # Deny on MongoDB failure
)
```

## When to Use MongoDB

Use MongoDB storage when:

- Your application already uses MongoDB
- You want to avoid adding Redis as a dependency
- You need the flexibility of MongoDB's query language
- You're using MongoDB Atlas for managed hosting

Use Redis when:

- You need lower latency (~1ms vs ~2ms)
- You need higher throughput (50K vs 20K req/s)
- You're using Redis for other purposes (caching, sessions)
