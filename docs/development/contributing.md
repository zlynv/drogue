# Contributing to drogue

## Development Setup

### Prerequisites

- Python 3.10+
- pip
- git

### Clone and Install

```bash
git clone https://github.com/Zlynv/drogue.git
cd drogue
pip install -e ".[dev,all]"
```

### Verify Installation

```bash
# Run tests
pytest

# Run linter
ruff check src/ tests/

# Run type checker
mypy src/
```

## Project Structure

```
drogue/
├── src/drogue/
│   ├── core/              # Core engine
│   │   ├── abstracts.py   # Abstract base classes
│   │   ├── algorithms/    # Rate limit algorithms
│   │   ├── config.py      # Configuration
│   │   ├── errors.py      # Exceptions
│   │   ├── headers.py     # Response headers
│   │   ├── identity/      # Identity extractors
│   │   ├── rules/         # Rule parsing
│   │   └── storage/       # Storage backends
│   ├── adapters/          # Framework adapters
│   │   ├── fastapi/
│   │   ├── django/
│   │   └── flask/
│   ├── protection/        # Protection layer
│   │   ├── ban.py         # Progressive auto-ban
│   │   ├── ddos.py        # DDoS detection
│   │   ├── trust.py       # Trust state machine
│   │   ├── sentinel.py    # Half-Space Trees
│   │   ├── probes.py      # Probe detection
│   │   ├── cidr.py        # CIDR filtering
│   │   └── adaptive.py    # Adaptive rate limiting
│   ├── defense/           # Defense mechanisms
│   │   └── randomizer.py  # Defense randomization
│   ├── storage/           # Advanced storage
│   │   └── probabilistic.py
│   └── observability/     # Observability
│       └── opentelemetry.py
├── tests/                 # Test suite
├── examples/              # Usage examples
├── docs/                  # Documentation
└── pyproject.toml
```

## Code Style

### Formatting

- Line length: 100 characters
- Use double quotes for strings
- Use trailing commas in collections

### Linting

```bash
# Check
ruff check src/ tests/

# Fix
ruff check --fix src/ tests/

# Format
ruff format src/ tests/
```

### Type Hints

All code must have complete type hints:

```python
def get_client_rate(self, client_key: str) -> float:
    """Get client's current request rate."""
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def record(self, client_key: str) -> None:
    """Record a request for a client.

    Args:
        client_key: The client identifier.
    """
    ...
```

## Adding a New Feature

### 1. Create a Branch

```bash
git checkout -b feature/my-feature
```

### 2. Write Tests First

```python
# tests/test_my_feature.py
import pytest

async def test_my_feature():
    # Arrange
    feature = MyFeature()

    # Act
    result = await feature.do_something()

    # Assert
    assert result == expected
```

### 3. Implement the Feature

Follow existing patterns in the codebase.

### 4. Run Tests

```bash
pytest tests/test_my_feature.py -v
```

### 5. Run Linter

```bash
ruff check src/ tests/
```

### 6. Create a Pull Request

- Describe what the PR does
- Reference any related issues
- Include tests for new functionality

## Testing

### Unit Tests

```bash
pytest tests/ -v
```

### With Coverage

```bash
pytest tests/ --cov=src/drogue --cov-report=html
```

### Specific Test

```bash
pytest tests/core/test_algorithms.py::TestTokenBucket::test_acquire_basic -v
```

### Integration Tests

```bash
cd _integration_test
python run_all.py
```

## Documentation

### Build Docs

```bash
pip install mkdocs-material
mkdocs serve
```

### View Docs

Open http://localhost:8000 in your browser.

## Release Process

1. Update version in `pyproject.toml`
2. Update `docs/development/changelog.md`
3. Create a git tag
4. Push to GitHub
5. Create a release on GitHub

## Questions?

Open an issue at https://github.com/Zlynv/drogue/issues
