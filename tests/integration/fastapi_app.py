"""FastAPI test app using drogue — exercises every feature."""
from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.config import DrogueConfig
from drogue.core.rules.rule import AlgorithmType
from drogue.protection.ban import ProgressiveBanManager
from drogue.protection.circuit import CircuitBreaker
from drogue.protection.ddos import DDoSDetector

config = DrogueConfig()
ddos = DDoSDetector(window=60.0, z_threshold=3.0, min_samples=5)
ban = ProgressiveBanManager(threshold=5, window=60.0)
circuit = CircuitBreaker(failure_threshold=3, recovery_timeout=5.0)

app = FastAPI(title="drogue FastAPI integration test")

limiter = DrogueLimiter(
    app,
    config=config,
    default_limits=["100/minute"],
)

storage = limiter.storage


# --- Basic rate limiting ---

@app.get("/api/ping")
@limiter.limit("10/minute")
async def ping():
    return {"status": "ok"}


@app.get("/api/slow")
@limiter.limit("5/minute", algorithm=AlgorithmType.SLIDING_WINDOW)
async def slow():
    return {"status": "ok"}


@app.get("/api/fixed")
@limiter.limit("5/minute", algorithm=AlgorithmType.FIXED_WINDOW)
async def fixed():
    return {"status": "ok"}


# --- Dependency injection ---

@app.get("/api/dep")
async def dep_route(_=Depends(limiter.dependency("5/minute"))):
    return {"status": "ok"}


# --- DDoS detection ---

@app.get("/api/ddos-check")
async def ddos_check():
    client_ip = "test_client"
    ddos.record(client_ip)
    is_attack = ddos.is_anomalous(client_ip)
    return {"is_anomalous": is_attack, "stats": ddos.get_stats()}


# --- Ban system ---

@app.get("/api/ban-check")
async def ban_check():
    key = "test_ban_key"
    if ban.is_banned(key):
        retry = ban.get_retry_after(key)
        return JSONResponse(
            {"error": "banned", "retry_after": retry},
            status_code=403,
        )
    return {"status": "ok"}


@app.post("/api/ban-violate")
async def ban_violate():
    key = "test_ban_key"
    level = ban.record_violation(key)
    return {"violation_level": level, "is_banned": ban.is_banned(key)}


@app.post("/api/ban-reset")
async def ban_reset():
    ban.clear_all()
    return {"status": "cleared"}


# --- Circuit breaker ---

_circuit_fail_count = 0

@app.get("/api/circuit-check")
async def circuit_check():
    global _circuit_fail_count
    if not circuit.allow_request():
        return JSONResponse(
            {"error": "circuit_open", "status": circuit.get_status()},
            status_code=503,
        )
    return {"status": "ok", "circuit": circuit.get_status()}


@app.post("/api/circuit-fail")
async def circuit_fail():
    global _circuit_fail_count
    circuit.record_failure()
    _circuit_fail_count += 1
    return {"failures": _circuit_fail_count, "circuit": circuit.get_status()}


@app.post("/api/circuit-success")
async def circuit_success():
    circuit.record_success()
    return {"circuit": circuit.get_status()}


@app.post("/api/circuit-reset")
async def circuit_reset():
    circuit.reset()
    global _circuit_fail_count
    _circuit_fail_count = 0
    return {"circuit": circuit.get_status()}


# --- Error handling ---

@app.get("/api/always-fail")
@limiter.limit("1/minute")
async def always_fail():
    raise ValueError("intentional error")


# --- Multiple limits on same route ---

@app.get("/api/multi")
@limiter.limit("10/minute")
@limiter.limit("3/second")
async def multi_limit():
    return {"status": "ok"}


# --- No rate limit ---

@app.get("/api/free")
async def free():
    return {"status": "ok"}
