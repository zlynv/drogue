"""Tests for FastAPI adapter."""
from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.rules.rule import AlgorithmType
from drogue.core.storage.memory import MemoryStorage


@pytest.fixture
def app() -> FastAPI:
    return FastAPI()


@pytest.fixture
def storage() -> MemoryStorage:
    return MemoryStorage()


@pytest.fixture
def limiter(app: FastAPI, storage: MemoryStorage) -> DrogueLimiter:
    return DrogueLimiter(app, storage=storage)


class TestBasicRateLimiting:
    """Test basic rate limiting functionality."""

    def test_limit_decorator(self, limiter: DrogueLimiter) -> None:
        assert limiter.storage is not None

    def test_rate_limit_headers_with_defaults(
        self, app: FastAPI, storage: MemoryStorage
    ) -> None:
        DrogueLimiter(app, storage=storage, default_limits=["5/minute"])

        @app.get("/test")
        async def test_route():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "5"

    def test_rate_limit_exceeded(self, limiter: DrogueLimiter, app: FastAPI) -> None:
        @app.get("/limited")
        @limiter.limit("2/minute")
        async def limited_route():
            return {"ok": True}

        client = TestClient(app)
        # First 2 requests should succeed
        assert client.get("/limited").status_code == 200
        assert client.get("/limited").status_code == 200
        # Third should be rate limited
        response = client.get("/limited")
        assert response.status_code == 429
        body = response.json()
        assert "retry_after" in body

    def test_separate_endpoints_independent(
        self, limiter: DrogueLimiter, app: FastAPI
    ) -> None:
        @app.get("/a")
        @limiter.limit("2/minute")
        async def route_a():
            return {"route": "a"}

        @app.get("/b")
        @limiter.limit("2/minute")
        async def route_b():
            return {"route": "b"}

        client = TestClient(app)
        # Exhaust /a
        assert client.get("/a").status_code == 200
        assert client.get("/a").status_code == 200
        assert client.get("/a").status_code == 429

        # /b should still work (separate bucket)
        assert client.get("/b").status_code == 200

    def test_different_algorithms(self, limiter: DrogueLimiter, app: FastAPI) -> None:
        @app.get("/token")
        @limiter.limit("2/minute", algorithm=AlgorithmType.TOKEN_BUCKET)
        async def token_route():
            return {"algo": "token_bucket"}

        @app.get("/sliding")
        @limiter.limit("2/minute", algorithm=AlgorithmType.SLIDING_WINDOW)
        async def sliding_route():
            return {"algo": "sliding_window"}

        @app.get("/fixed")
        @limiter.limit("2/minute", algorithm=AlgorithmType.FIXED_WINDOW)
        async def fixed_route():
            return {"algo": "fixed_window"}

        @app.get("/gcra")
        @limiter.limit("2/minute", algorithm=AlgorithmType.GCRA)
        async def gcra_route():
            return {"algo": "gcra"}

        @app.get("/leaky")
        @limiter.limit("2/minute", algorithm=AlgorithmType.LEAKY_BUCKET)
        async def leaky_route():
            return {"algo": "leaky_bucket"}

        client = TestClient(app)
        assert client.get("/token").status_code == 200
        assert client.get("/sliding").status_code == 200
        assert client.get("/fixed").status_code == 200
        assert client.get("/gcra").status_code == 200
        assert client.get("/leaky").status_code == 200


class TestDependencyInjection:
    """Test FastAPI Depends() integration."""

    def test_dependency_rate_limit(self, limiter: DrogueLimiter, app: FastAPI) -> None:
        @app.get("/dep")
        async def dep_route(_=Depends(limiter.dependency("2/minute"))):
            return {"ok": True}

        client = TestClient(app)
        assert client.get("/dep").status_code == 200
        assert client.get("/dep").status_code == 200
        assert client.get("/dep").status_code == 429

    def test_dependency_with_path_param(
        self, limiter: DrogueLimiter, app: FastAPI
    ) -> None:
        @app.get("/items/{item_id}")
        async def item_route(
            item_id: int, _=Depends(limiter.dependency("3/minute"))
        ):
            return {"item_id": item_id}

        client = TestClient(app)
        assert client.get("/items/1").status_code == 200
        assert client.get("/items/2").status_code == 200
        assert client.get("/items/3").status_code == 200
        assert client.get("/items/4").status_code == 429


class TestNoRequestSignature:
    """Test that decorators don't require request: Request in user code."""

    def test_clean_signature(self, limiter: DrogueLimiter, app: FastAPI) -> None:
        @app.get("/clean")
        @limiter.limit("5/minute")
        async def clean_route():
            """No request parameter needed."""
            return {"clean": True}

        # The wrapper injects a hidden `request` kwarg for internal use,
        # but the user's function doesn't need to declare it.
        import inspect
        sig = inspect.signature(clean_route)
        assert "request" in sig.parameters  # injected by limiter

        # The route works without the user declaring request
        client = TestClient(app)
        response = client.get("/clean")
        assert response.status_code == 200


class TestDefaultLimits:
    """Test global default limits."""

    def test_default_limits(self, app: FastAPI, storage: MemoryStorage) -> None:
        DrogueLimiter(
            app,
            storage=storage,
            default_limits=["3/minute"],
        )

        @app.get("/a")
        async def route_a():
            return {"a": True}

        @app.get("/b")
        async def route_b():
            return {"b": True}

        client = TestClient(app)
        # Should share the global limit
        assert client.get("/a").status_code == 200
        assert client.get("/b").status_code == 200
        assert client.get("/a").status_code == 200
        assert client.get("/a").status_code == 429  # 4th request


class TestErrorHandling:
    """Test error response format."""

    def test_429_response_body(self, limiter: DrogueLimiter, app: FastAPI) -> None:
        @app.get("/error")
        @limiter.limit("1/minute")
        async def error_route():
            return {"ok": True}

        client = TestClient(app)
        assert client.get("/error").status_code == 200
        response = client.get("/error")
        assert response.status_code == 429
        body = response.json()
        assert "error" in body
        assert "retry_after" in body


class TestProtectionPipeline:
    """Test pipeline integration with FastAPI adapter."""

    def test_banned_client_blocked(self, app: FastAPI) -> None:
        from drogue.protection.ban import ProgressiveBanManager
        from drogue.protection.pipeline import ProtectionPipeline

        ban = ProgressiveBanManager(threshold=1, window=60.0)
        pipeline = ProtectionPipeline(ban=ban)
        limiter = DrogueLimiter(app, storage=MemoryStorage(), pipeline=pipeline)

        @app.get("/pipelined")
        @limiter.limit("10/minute")
        async def pipelined_route():
            return {"ok": True}

        # Ban the client
        ban.record_violation("testclient")

        client = TestClient(app)
        response = client.get("/pipelined")
        assert response.status_code == 403
        assert response.json()["error"] == "banned"

    def test_circuit_open_blocked(self, app: FastAPI) -> None:
        from drogue.protection.circuit import CircuitBreaker
        from drogue.protection.pipeline import ProtectionPipeline

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)
        pipeline = ProtectionPipeline(circuit=cb)
        limiter = DrogueLimiter(app, storage=MemoryStorage(), pipeline=pipeline)

        @app.get("/circuit-piped")
        @limiter.limit("10/minute")
        async def circuit_route():
            return {"ok": True}

        # Trip the circuit
        cb.record_failure()
        cb.record_failure()

        client = TestClient(app)
        response = client.get("/circuit-piped")
        assert response.status_code == 503
        assert response.json()["error"] == "circuit_open"

    def test_violation_recorded_on_rate_limit(self, app: FastAPI) -> None:
        from drogue.protection.ban import ProgressiveBanManager
        from drogue.protection.pipeline import ProtectionPipeline

        ban = ProgressiveBanManager(threshold=3, window=60.0)
        pipeline = ProtectionPipeline(ban=ban)
        limiter = DrogueLimiter(app, storage=MemoryStorage(), pipeline=pipeline)

        @app.get("/violation")
        @limiter.limit("2/minute")
        async def violation_route():
            return {"ok": True}

        client = TestClient(app)
        # Exhaust rate limit
        assert client.get("/violation").status_code == 200
        assert client.get("/violation").status_code == 200
        response = client.get("/violation")
        assert response.status_code == 429

        # Pipeline should have recorded the violation
        assert ban.is_banned("testclient") or len(ban._violations.get("testclient", [])) > 0

    def test_no_pipeline_still_works(self, app: FastAPI) -> None:
        limiter = DrogueLimiter(app, storage=MemoryStorage())

        @app.get("/no-pipeline")
        @limiter.limit("2/minute")
        async def no_pipeline_route():
            return {"ok": True}

        client = TestClient(app)
        assert client.get("/no-pipeline").status_code == 200
        assert client.get("/no-pipeline").status_code == 200
        assert client.get("/no-pipeline").status_code == 429
