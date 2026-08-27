"""Drogue - Modern rate limiting and application-layer protection for Python.

Usage:
    from drogue import DrogueLimiter, RateLimitRule

    # FastAPI
    app = FastAPI()
    limiter = DrogueLimiter(app)

    @app.get("/api/data")
    @limiter.limit("100/minute")
    async def get_data():
        return {"data": "value"}
"""

from __future__ import annotations

from drogue.core.abstracts import AcquireResult, Algorithm, IdentityExtractor, Storage
from drogue.core.algorithms import (
    FixedWindowAlgorithm,
    SlidingWindowAlgorithm,
    TokenBucketAlgorithm,
)
from drogue.core.config import DrogueConfig
from drogue.core.errors import (
    BackendFailure,
    BanError,
    ConfigurationError,
    RateLimitExceeded,
    StorageError,
)
from drogue.core.identity import (
    CompositeExtractor,
    HeaderExtractor,
    RemoteAddressExtractor,
    UserExtractor,
)
from drogue.core.rules.rule import AlgorithmType, RateLimitRule, parse_rule_string
from drogue.core.storage.memory import MemoryStorage

__version__ = "0.3.0"

__all__ = [
    # Core
    "Algorithm",
    "Storage",
    "IdentityExtractor",
    "AcquireResult",
    # Config
    "DrogueConfig",
    # Errors
    "RateLimitExceeded",
    "BackendFailure",
    "BanError",
    "ConfigurationError",
    "StorageError",
    # Rules
    "RateLimitRule",
    "AlgorithmType",
    "parse_rule_string",
    # Storage
    "MemoryStorage",
    # Algorithms
    "TokenBucketAlgorithm",
    "SlidingWindowAlgorithm",
    "FixedWindowAlgorithm",
    # Identity
    "RemoteAddressExtractor",
    "UserExtractor",
    "HeaderExtractor",
    "CompositeExtractor",
    # Version
    "__version__",
]
