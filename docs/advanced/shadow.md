# Shadow Mode

## Overview

Shadow Mode allows evaluating rate limit rules without enforcing them. This is useful for testing new rules in production without affecting users.

## Usage

```python
# Global shadow mode
from drogue.core.config import DrogueConfig

config = DrogueConfig(shadow_enabled=True)
limiter = DrogueLimiter(app, config=config)
```

## Per-Route Shadow Mode

```python
@app.get("/api/data")
@limiter.limit("10/minute", shadow=True)
async def get_data():
    return {"data": "value"}
```

## Checking What Would Have Been Blocked

```python
# Get shadow mode statistics
stats = limiter.get_shadow_stats()
# {"api/data": 42}  # 42 requests would have been blocked

# Clear statistics
limiter.clear_shadow_stats()
```

## How It Works

1. Request arrives
2. Rate limit check is performed
3. If shadow mode is enabled, the result is logged but not enforced
4. Request is always allowed (regardless of rate limit result)
5. Statistics are updated

## Use Cases

- **Testing new rules:** Deploy rules to production without affecting users
- **Capacity planning:** See how many requests would be blocked
- **Rule tuning:** Adjust limits based on real traffic patterns
- **Safe rollout:** Gradually enable enforcement after validation

## Integration with drogue

```python
class DrogueLimiter:
    async def _check(self, key, rule, context, route_key=""):
        algo = self._get_algorithm(rule, route_key)
        cost = await CostResolver.resolve_cost(rule, context)
        rule_id = f"{rule.algorithm.value}:{rule.limit}:{rule.window}"
        storage_key = f"{route_key}:{rule_id}:{key}" if route_key else key
        result = await algo.acquire(storage_key, cost=cost, block=rule.block, timeout=rule.timeout)

        # Shadow mode: log but don't enforce
        if rule.shadow or self.config.shadow_enabled:
            shadow_key = route_key or "global"
            self._shadow_stats[shadow_key] = self._shadow_stats.get(shadow_key, 0) + 1
            if not result.allowed:
                logger.info(
                    "shadow_mode: would have blocked key=%s route=%s retry_after=%.1f",
                    key,
                    shadow_key,
                    result.retry_after or 0,
                )
            # Always allow in shadow mode
            return AcquireResult(
                allowed=True,
                limit=result.limit,
                remaining=result.remaining,
                retry_after=0,
                headers=result.headers,
            )

        return result
```
