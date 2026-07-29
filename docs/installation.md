---
description: Install drogue rate limiting library for Python. Supports FastAPI, Django, Flask with optional Redis backend.
---

# Installation

## Requirements

- Python 3.10 or later
- No external dependencies for core functionality

drogue has **zero runtime dependencies** for the core rate limiting engine. Framework adapters, storage backends, and observability integrations are installed as optional extras.

## Install from PyPI

```bash
pip install drogue
```

## Framework extras

```bash
pip install drogue[fastapi]   # FastAPI + Starlette
pip install drogue[django]    # Django
pip install drogue[flask]     # Flask
pip install drogue[drf]       # Django REST Framework
```

## Storage extras

```bash
pip install drogue[redis]     # Redis backend (redis[hiredis] >= 5.0)
```

## Observability extras

```bash
pip install drogue[prometheus]       # Prometheus metrics
pip install drogue[opentelemetry]    # OpenTelemetry tracing
pip install drogue[adaptive]         # CPU/memory adaptive limits (psutil)
```

## Install everything

```bash
pip install drogue[all]
```

## Development install

```bash
git clone https://github.com/zlynv/drogue.git
cd drogue
pip install -e ".[dev]"
```

## Verify

```python
import drogue
print(drogue.__version__)
```
