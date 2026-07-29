# Serverless Deployment

drogue works in serverless environments (AWS Lambda, Google Cloud Functions, Azure Functions, Vercel, etc.). There are a few things to understand about how rate limiting works when your application starts and stops with each request.

## How It Works

In serverless, each invocation is an isolated process. drogue's in-memory storage is per-invocation, so rate limit state does not persist between cold starts.

This is fine for most use cases:

- **Per-user limits**: Each user's limit is tracked across invocations via Redis
- **Global limits**: Work if you use Redis storage
- **DDoS detection**: Works with Redis storage
- **Auto-banning**: Works with Redis storage

If you use in-memory storage only, limits are approximate. A user might get slightly more requests than intended during cold starts.

## FastAPI (AWS Lambda)

```bash
pip install drogue[fastapi,redis]
```

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.storage.redis import RedisStorage

app = FastAPI()

# Use Redis for persistent state across invocations
storage = RedisStorage(url="redis://your-redis-endpoint:6379")

limiter = DrogueLimiter(
    app,
    storage=storage,
    rules=["100/minute", "1000/hour"],
)

@app.get("/api/data")
@limiter.limit("10/second")
async def get_data():
    return {"data": "value"}
```

## Google Cloud Functions

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.storage.redis import RedisStorage

app = FastAPI()

# Use Memorystore Redis or Cloud Redis
storage = RedisStorage(url="redis://10.0.0.3:6379")

limiter = DrogueLimiter(
    app,
    storage=storage,
    rules=["100/minute"],
)
```

## Azure Functions

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.storage.redis import RedisStorage

app = FastAPI()

# Use Azure Cache for Redis
storage = RedisStorage(url="redis://your-redis.redis.cache.windows.net:6380")

limiter = DrogueLimiter(
    app,
    storage=storage,
    rules=["100/minute"],
)
```

## Vercel / Netlify

```python
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.storage.redis import RedisStorage

app = FastAPI()

# Use Upstash Redis (serverless-friendly)
storage = RedisStorage(url="redis://default:password@your-upstash.redis.io:6379")

limiter = DrogueLimiter(
    app,
    storage=storage,
    rules=["100/minute"],
)
```

## In-Memory Only

If you do not need cross-invocation persistence, in-memory works:

```python
limiter = DrogueLimiter(
    app,
    storage="memory://",
    rules=["100/minute"],
)
```

Limits are per-invocation. A user might get 100 requests per Lambda cold start, not per minute overall. This is acceptable for low-security use cases.

## Redis Providers for Serverless

| Provider | Free Tier | Best For |
|----------|-----------|----------|
| [Upstash](https://upstash.com) | 10K commands/day | Vercel, Netlify |
| [Redis Cloud](https://redis.com) | 30MB free | AWS, GCP, Azure |
| [Memorystore](https://cloud.google.com/memorystore) | No free tier | GCP |
| [ElastiCache](https://aws.amazon.com/elasticache/) | No free tier | AWS |
| [Azure Cache](https://azure.microsoft.com/products/cache) | No free tier | Azure |

## Cold Start Impact

drogue adds minimal cold start overhead:

| Component | Cold Start | Warm |
|-----------|------------|------|
| Import + init | ~2ms | 0ms |
| Redis connection | ~10ms | 0ms (pooled) |
| First request | ~15ms | ~1.4us |

The Redis connection is established on first use and pooled for subsequent invocations.

## Environment Variables

Store Redis URL in environment variables:

```python
import os
from drogue.core.storage.redis import RedisStorage

storage = RedisStorage(url=os.environ["REDIS_URL"])
```

Lambda:

```bash
aws lambda update-function-configuration \
  --function-name my-function \
  --environment "Variables={REDIS_URL=redis://your-endpoint:6379}"
```

Cloud Functions:

```bash
gcloud functions deploy my-function \
  --set-env-vars REDIS_URL=redis://your-endpoint:6379
```

## Notes

- MemoryStorage resets on cold start — use Redis for production
- DDoS detection needs Redis to track traffic across invocations
- Auto-ban state is lost on cold start without Redis
- Circuit breaker state is per-invocation with in-memory storage
- Trust scores need Redis to persist across invocations
