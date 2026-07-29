# Testing Guide

## Test Structure

```
tests/
├── core/
│   ├── test_algorithms.py      # Rate limit algorithm tests
│   ├── test_config.py          # Configuration tests
│   ├── test_storage.py         # Storage backend tests
│   ├── test_rules.py           # Rule parsing tests
│   └── test_cost_resolver.py   # Cost resolver tests
├── adapters/
│   ├── test_fastapi.py         # FastAPI adapter tests
│   ├── test_flask.py           # Flask adapter tests
│   └── test_django.py          # Django adapter tests
├── protection/
│   ├── test_ban.py             # Auto-ban tests
│   ├── test_ddos.py            # DDoS detection tests
│   ├── test_trust.py           # Trust state tests
│   ├── test_sentinel.py        # Sentinel model tests
│   ├── test_probes.py          # Probe detection tests
│   └── test_cidr.py            # CIDR filtering tests
├── test_regressions.py         # Regression tests
└── _integration_test/          # Integration tests
    ├── run_all.py              # Test runner
    ├── test_fastapi_integration.py
    ├── test_django_integration.py
    └── test_redis_integration.py
```

## Running Tests

### All Tests

```bash
pytest
```

### Verbose Output

```bash
pytest -v
```

### Specific Test File

```bash
pytest tests/core/test_algorithms.py -v
```

### Specific Test

```bash
pytest tests/core/test_algorithms.py::TestTokenBucket::test_acquire_basic -v
```

### With Coverage

```bash
pytest --cov=src/drogue --cov-report=html
```

### Parallel Execution

```bash
pytest -n auto
```

## Test Types

### Unit Tests

Fast, isolated tests for individual components:

```python
import pytest

async def test_token_bucket_acquire():
    storage = MemoryStorage()
    await storage.initialize()
    algo = TokenBucketAlgorithm(storage, capacity=10, refill_rate=1.0)

    result = await algo.acquire("key1")

    assert result.allowed is True
    assert result.remaining == 9
```

### Integration Tests

Tests that verify multiple components working together:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

async def test_fastapi_rate_limit():
    app = FastAPI()
    limiter = DrogueLimiter(app)

    @app.get("/test")
    @limiter.limit("2/second")
    async def test_endpoint():
        return {"ok": True}

    client = TestClient(app)

    # First two requests should pass
    response = client.get("/test")
    assert response.status_code == 200

    # Third request should be blocked
    response = client.get("/test")
    assert response.status_code == 429
```

### Regression Tests

Tests that verify specific bug fixes:

```python
async def test_token_bucket_no_leak():
    """Regression: Token bucket was leaking tokens due to fractional truncation."""
    storage = MemoryStorage()
    await storage.initialize()
    algo = TokenBucketAlgorithm(storage, capacity=10, refill_rate=1.0)

    # Drain tokens
    for _ in range(10):
        await algo.acquire("key1")

    # Wait for partial refill
    await asyncio.sleep(0.5)

    # Should have ~0.5 tokens, not 0
    result = await algo.acquire("key1")
    assert result.allowed is True
```

## Test Fixtures

### Storage Fixtures

```python
@pytest.fixture
def memory_storage():
    return MemoryStorage()

@pytest.fixture
async def redis_storage():
    storage = RedisStorage(url="redis://localhost:6379")
    await storage.initialize()
    yield storage
    await storage.close()
```

### Limiter Fixtures

```python
@pytest.fixture
def fastapi_limiter():
    app = FastAPI()
    return DrogueLimiter(app)

@pytest.fixture
def flask_limiter():
    app = Flask(__name__)
    return DrogueLimiter(app)
```

### Mock Fixtures

```python
@pytest.fixture
def mock_context():
    return {
        "client": {"host": "192.168.1.1"},
        "method": "GET",
        "path": "/api/data",
        "headers": {"user-agent": "test"},
    }
```

## Writing Tests

### Naming Convention

```python
# Test file: test_<module>.py
# Test class: Test<Component>
# Test method: test_<action>_<scenario>

class TestTokenBucket:
    def test_acquire_basic(self):
        ...

    def test_acquire_after_refill(self):
        ...

    def test_acquire_when_empty(self):
        ...
```

### Assertions

```python
# Use specific assertions
assert result.allowed is True
assert result.remaining == 9
assert result.retry_after == 0.0

# Not
assert result
```

### Async Tests

```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result == expected
```

### Parametrized Tests

```python
@pytest.mark.parametrize("limit,window,expected", [
    ("10/minute", 60.0, 10),
    ("100/hour", 3600.0, 100),
    ("1/second", 1.0, 1),
])
def test_rule_parsing(limit, window, expected):
    rule = parse_rule_string(limit)
    assert rule.limit == expected
    assert rule.window == window
```

## Test Data

### Rate Limit Strings

```python
TEST_RATE_LIMITS = [
    ("10/minute", 10, 60.0),
    ("100/hour", 100, 3600.0),
    ("1/second", 1, 1.0),
    ("10/second;100/minute", 10, 1.0),
]
```

### Client IDs

```python
TEST_CLIENTS = [
    "192.168.1.1",
    "10.0.0.1",
    "user:12345",
    "session:abc123",
]
```

## Coverage

### Generate Report

```bash
pytest --cov=src/drogue --cov-report=html --cov-report=term
```

### Coverage Requirements

- Core algorithms: 100%
- Storage backends: 100%
- Adapters: 95%+
- Protection layer: 95%+

### View Report

```bash
open htmlcov/index.html
```

## CI/CD

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: pip install -e ".[dev,all]"
      - name: Run tests
        run: pytest --cov=src/drogue
      - name: Run linter
        run: ruff check src/ tests/
```

## Debugging Tests

### Verbose Output

```bash
pytest -v -s
```

### Stop on First Failure

```bash
pytest -x
```

### Run Last Failed

```bash
pytest --lf
```

### Drop to Debugger

```bash
pytest --pdb
```

### Print stdout

```bash
pytest -s -v
```
