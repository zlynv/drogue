"""FastAPI benchmark app with DDoS protection features.

Run with:
    python -m uvicorn benchmarks.apps.ddos_app:app --port 8000
"""
import time
from collections import defaultdict

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.rules.rule import AlgorithmType
from drogue.core.storage.memory import MemoryStorage
from drogue.protection.ban import ProgressiveBanManager
from drogue.protection.circuit import CircuitBreaker
from drogue.protection.ddos import DDoSDetector

app = FastAPI(title="drogue DDoS Benchmark")

# Storage
storage = MemoryStorage()

# Rate limiter
limiter = DrogueLimiter(
    app,
    storage=storage,
    default_limits=["100000/minute"],
)

# DDoS protection components
ddos = DDoSDetector(window=60.0, z_threshold=3.0, min_clients=10)
ban = ProgressiveBanManager(threshold=5, window=60.0)
circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=10.0)

# Stats tracking
stats = {
    "start_time": time.monotonic(),
    "requests": defaultdict(lambda: {"count": 0, "errors": 0, "bans": 0, "ddos_blocked": 0}),
    "total_requests": 0,
    "total_errors": 0,
    "total_bans": 0,
    "total_ddos_blocked": 0,
}


@app.middleware("http")
async def ddos_protection(request: Request, call_next):
    client_ip = request.client.host if request.client else "127.0.0.1"
    path = request.url.path

    # Skip protected endpoints
    if path in ("/stats", "/stats/html", "/health", "/api/ban-reset", "/api/ban-check", "/api/ddos-stats", "/api/circuit-status"):
        return await call_next(request)

    # Always record request for DDoS detection (even if banned)
    ddos.record(client_ip)

    # Check if client is banned (AFTER recording for DDoS)
    if ban.is_banned(client_ip):
        stats["total_bans"] += 1
        stats["requests"][path]["bans"] += 1
        retry_after = ban.get_retry_after(client_ip)
        return JSONResponse(
            {"error": "Banned", "retry_after": retry_after},
            status_code=403,
        )

    # Check if DDoS detected
    if ddos.is_anomalous(client_ip):
        stats["total_ddos_blocked"] += 1
        stats["requests"][path]["ddos_blocked"] += 1
        ban.record_violation(client_ip)
        return JSONResponse(
            {"error": "DDoS detected", "client": client_ip},
            status_code=429,
        )

    # Check circuit breaker
    if not circuit.allow_request():
        return JSONResponse(
            {"error": "Circuit breaker open", "status": circuit.get_status()},
            status_code=503,
        )

    stats["total_requests"] += 1
    stats["requests"][path]["count"] += 1

    response = await call_next(request)

    # Record 429s as errors and record violations
    if response.status_code == 429:
        stats["total_errors"] += 1
        stats["requests"][path]["errors"] += 1
        ban.record_violation(client_ip)
        circuit.record_failure()
    else:
        circuit.record_success()

    return response


@app.get("/api/data")
@limiter.limit("100/second", algorithm=AlgorithmType.TOKEN_BUCKET)
async def get_data():
    return {"data": "value", "algorithm": "token_bucket"}


@app.get("/api/heavy")
@limiter.limit("50/second", algorithm=AlgorithmType.SLIDING_WINDOW)
async def heavy():
    return {"data": "x" * 1000, "algorithm": "sliding_window"}


@app.get("/api/free")
async def free():
    return {"data": "no-limit"}


@app.get("/api/ban-check")
async def ban_check(request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    return {
        "client": client_ip,
        "is_banned": ban.is_banned(client_ip),
        "retry_after": ban.get_retry_after(client_ip) if ban.is_banned(client_ip) else None,
    }


@app.post("/api/ban-reset")
async def ban_reset():
    ban.clear_all()
    return {"status": "cleared"}


@app.get("/api/ddos-stats")
async def ddos_stats():
    return ddos.get_stats()


@app.get("/api/circuit-status")
async def circuit_status():
    return {"status": circuit.get_status()}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/stats")
async def get_stats():
    uptime = time.monotonic() - stats["start_time"]
    return {
        "uptime_seconds": round(uptime, 1),
        "total_requests": stats["total_requests"],
        "total_errors": stats["total_errors"],
        "total_bans": stats["total_bans"],
        "total_ddos_blocked": stats["total_ddos_blocked"],
        "requests_per_second": round(stats["total_requests"] / max(1, uptime), 1),
        "endpoints": dict(stats["requests"]),
    }


@app.get("/stats/html", response_class=HTMLResponse)
async def get_stats_html():
    uptime = time.monotonic() - stats["start_time"]
    rps = stats["total_requests"] / max(1, uptime)

    rows = ""
    for name, data in stats["requests"].items():
        rows += f"""
        <tr>
            <td>{name}</td>
            <td>{data['count']:,}</td>
            <td>{data['errors']:,}</td>
            <td>{data['bans']:,}</td>
            <td>{data['ddos_blocked']:,}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>drogue DDoS Benchmark Stats</title>
    <meta http-equiv="refresh" content="2">
    <style>
        body {{ font-family: monospace; margin: 40px; background: #1a1a1a; color: #0f0; }}
        h1 {{ color: #0f0; }}
        h2 {{ color: #ff0; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #333; padding: 8px 12px; text-align: left; }}
        th {{ background: #222; }}
        .stat {{ margin: 10px 0; }}
        .label {{ color: #888; }}
        .value {{ color: #0f0; font-size: 1.2em; }}
        .warning {{ color: #ff0; }}
        .danger {{ color: #f00; }}
    </style>
</head>
<body>
    <h1>drogue DDoS Benchmark Stats</h1>
    <div class="stat"><span class="label">Uptime:</span> <span class="value">{uptime:.0f}s</span></div>
    <div class="stat"><span class="label">Total Requests:</span> <span class="value">{stats['total_requests']:,}</span></div>
    <div class="stat"><span class="label">Rate Limited (429):</span> <span class="value warning">{stats['total_errors']:,}</span></div>
    <div class="stat"><span class="label">Banned (403):</span> <span class="value danger">{stats['total_bans']:,}</span></div>
    <div class="stat"><span class="label">DDoS Blocked:</span> <span class="value danger">{stats['total_ddos_blocked']:,}</span></div>
    <div class="stat"><span class="label">Requests/sec:</span> <span class="value">{rps:.1f}</span></div>

    <h2>Protection Status</h2>
    <div class="stat"><span class="label">DDoS Detector:</span> <span class="value">Active (Z-score > 3.0)</span></div>
    <div class="stat"><span class="label">Ban Manager:</span> <span class="value">Active (threshold: 5 violations)</span></div>
    <div class="stat"><span class="label">Circuit Breaker:</span> <span class="value">{circuit.get_status()}</span></div>

    <h2>Per-Endpoint Stats</h2>
    <table>
        <tr>
            <th>Endpoint</th>
            <th>Requests</th>
            <th>Rate Limited</th>
            <th>Banned</th>
            <th>DDoS Blocked</th>
        </tr>
        {rows}
    </table>
    <p style="color: #666; margin-top: 20px;">Auto-refreshes every 2 seconds</p>
</body>
</html>"""
