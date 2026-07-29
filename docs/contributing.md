# Contributing

## Development setup

```bash
git clone https://github.com/zlynv/drogue.git
cd drogue
pip install -e ".[dev]"
```

## Running tests

```bash
# Unit tests
pytest

# With coverage
pytest --cov=src/drogue

# Specific test
pytest tests/core/test_algorithms.py::TestTokenBucket::test_acquire_basic -v
```

## Linting

```bash
# Check
ruff check src/ tests/

# Fix
ruff check --fix src/ tests/

# Format
ruff format src/ tests/
```

## Type checking

```bash
mypy src/
```

## Project structure

```
src/drogue/
    core/           # Rate limiting engine
    adapters/       # Framework integrations
    protection/     # Security features
    defense/        # Adversarial defenses
    storage/        # Probabilistic data structures
    observability/  # Metrics, logging, tracing
```

## Code style

- Line length: 100 characters
- Double quotes for strings
- Complete type hints on all public APIs
- Google-style docstrings

## Pull request process

1. Create a branch from `main`
2. Write tests for new functionality
3. Run `ruff check` and `pytest`
4. Submit PR with clear description

## Release process

1. Update version in `pyproject.toml`
2. Update `docs/changelog.md`
3. Create git tag
4. Push to GitHub
5. Publish to PyPI: `python -m build && twine upload dist/*`
