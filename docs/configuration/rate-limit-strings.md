# Rate Limit Strings

## Format

Rate limit strings follow the format: `{limit}/{unit}` or `{limit}/{window}{unit}`

```python
@limiter.limit("100/minute")
@limiter.limit("10/second")
@limiter.limit("1000/hour")
@limiter.limit("10000/day")

# Extended format: specify custom window duration
@limiter.limit("100/30s")   # 100 requests per 30 seconds
@limiter.limit("50/15m")    # 50 requests per 15 minutes
@limiter.limit("1000/2h")   # 1000 requests per 2 hours
@limiter.limit("500/3d")    # 500 requests per 3 days
```

## Units

| Unit | Abbreviation | Duration |
|------|--------------|----------|
| second | s | 1 second |
| minute | m | 60 seconds |
| hour | h | 3600 seconds |
| day | d | 86400 seconds |

When a numeric prefix is provided before the unit (e.g., `30s`, `15m`, `2h`, `3d`), it multiplies the base unit. For example, `100/30s` = 100 requests per 30 seconds, `50/15m` = 50 requests per 900 seconds.

## Units

| Unit | Abbreviation | Duration |
|------|--------------|----------|
| second | s | 1 second |
| minute | m | 60 seconds |
| hour | h | 3600 seconds |
| day | d | 86400 seconds |

## Examples

```python
# Requests per second
@limiter.limit("10/second")
@limiter.limit("10/s")

# Requests per minute
@limiter.limit("100/minute")
@limiter.limit("100/m")

# Requests per hour
@limiter.limit("1000/hour")
@limiter.limit("1000/h")

# Requests per day
@limiter.limit("10000/day")
@limiter.limit("10000/d")
```

## Parsing

Rate limit strings are parsed by `parse_rule_string()`:

```python
from drogue.core.rules.rule import parse_rule_string

rule = parse_rule_string("100/minute")
# rule.limit = 100
# rule.window = 60.0
```

## Default Limits

Default limits apply to all routes:

```python
limiter = DrogueLimiter(
    app,
    default_limits=["100/minute"],
)
```

## Multiple Limits

You can apply multiple limits to a single route:

```python
@app.get("/api/data")
@limiter.limit("100/minute")
@limiter.limit("1000/hour")
async def get_data():
    return {"data": "value"}
```
