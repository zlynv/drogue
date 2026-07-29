# Circuit Breaker

## What is a circuit breaker?

A circuit breaker prevents cascading failures by stopping requests to a failing service. When failures exceed a threshold, the circuit "opens" and all requests are immediately denied. After a recovery timeout, it enters "half-open" state and allows one probe request. If the probe succeeds, the circuit closes; if it fails, it opens again.

## Why it matters

Without a circuit breaker, a failing service causes:
- Request timeouts piling up
- Resource exhaustion
- Cascading failures across your system

The circuit breaker fails fast, preserving resources and giving the failing service time to recover.

## States

```
CLOSED (normal) --[failures >= threshold]--> OPEN (blocking)
     ^                                            |
     |                                      [timeout]
     |                                            v
     +--[probe success]-- HALF-OPEN --[probe failure]--> OPEN
```

| State | Behavior |
|-------|----------|
| CLOSED | Normal operation, requests pass through |
| OPEN | All requests denied immediately |
| HALF-OPEN | Allows one probe request to test recovery |

## Usage

```python
from drogue.protection.circuit import CircuitBreaker

breaker = CircuitBreaker(
    failure_threshold=5,      # Failures before opening
    recovery_timeout=30.0,    # Seconds before half-open
    jitter=0.2,               # Random jitter on timeout
    half_open_max_calls=1,    # Probes allowed in half-open
)

# Check if request is allowed
if breaker.allow_request():
    try:
        result = call_external_service()
        breaker.record_success()
    except Exception:
        breaker.record_failure()
else:
    # Circuit is open, fail fast
    return {"error": "Service unavailable", "retry_after": 30}
```

## Response examples

### `get_status()` response

```python
status = breaker.get_status()
# {
#     "state": "closed",           # Current state
#     "failure_count": 0,          # Consecutive failures
#     "success_count": 42,         # Consecutive successes
#     "last_failure_time": None,   # Timestamp of last failure
#     "half_open_calls": 0,        # Probes in half-open
# }
```

### `state.value` response

```python
breaker.state.value
# "closed"    -- normal operation
# "open"      -- blocking all requests
# "half_open" -- testing recovery
```

## State transitions

```
1. Start in CLOSED state
2. Each failure increments failure_count
3. When failure_count >= failure_threshold:
   - State changes to OPEN
   - All requests denied
4. After recovery_timeout seconds:
   - State changes to HALF-OPEN
   - One probe request is allowed
5. If probe succeeds:
   - State changes to CLOSED
   - failure_count resets to 0
6. If probe fails:
   - State changes back to OPEN
   - recovery_timeout restarts
```

## Manual operations

```python
# Force reset to closed
breaker.reset()

# Check current state
if breaker.state.value == "open":
    print("Circuit is open, failing fast")
```

## Configuration

```python
from drogue.core.config import DrogueConfig

config = DrogueConfig(
    circuit_breaker_enabled=True,
    circuit_failure_threshold=5,
    circuit_recovery_timeout=30.0,
    circuit_jitter=0.2,
)
```

## Example: External API protection

```python
from drogue.protection.circuit import CircuitBreaker
import httpx

breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)

async def call_payment_api(data):
    if not breaker.allow_request():
        raise Exception("Payment API unavailable, try again later")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post("https://api.payments.com/charge", json=data)
            response.raise_for_status()
            breaker.record_success()
            return response.json()
    except Exception as e:
        breaker.record_failure()
        raise
```
