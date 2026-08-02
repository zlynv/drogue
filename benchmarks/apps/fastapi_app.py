"""FastAPI benchmark app with drogue rate limiting.

Run with:
    python -m uvicorn benchmarks.apps.fastapi_app:app --port 8000
    python -m uvicorn benchmarks.apps.fastapi_app:app --port 8000 --workers 4
"""
import time
from collections import defaultdict

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.rules.rule import AlgorithmType
from drogue.core.storage.memory import MemoryStorage

app = FastAPI(title="drogue Benchmark")

storage = MemoryStorage()

limiter = DrogueLimiter(
    app,
    storage=storage,
    default_limits=["100000/minute"],
)

# Request tracking
stats = {
    "start_time": time.monotonic(),
    "requests": defaultdict(lambda: {"count": 0, "errors": 0, "total_time": 0}),
    "total_requests": 0,
    "total_errors": 0,
}


@app.middleware("http")
async def track_requests(request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    elapsed = (time.monotonic() - start) * 1000

    path = request.url.path
    stats["total_requests"] += 1
    stats["requests"][path]["count"] += 1
    stats["requests"][path]["total_time"] += elapsed

    if response.status_code == 429:
        stats["total_errors"] += 1
        stats["requests"][path]["errors"] += 1

    return response


@app.get("/api/token-bucket")
@limiter.limit("100/second", algorithm=AlgorithmType.TOKEN_BUCKET)
async def token_bucket():
    return {"data": "value", "algorithm": "token_bucket"}


@app.get("/api/sliding-window")
@limiter.limit("100/second", algorithm=AlgorithmType.SLIDING_WINDOW)
async def sliding_window():
    return {"data": "value", "algorithm": "sliding_window"}


@app.get("/api/fixed-window")
@limiter.limit("100/second", algorithm=AlgorithmType.FIXED_WINDOW)
async def fixed_window():
    return {"data": "value", "algorithm": "fixed_window"}


@app.get("/api/heavy")
@limiter.limit("50/second", algorithm=AlgorithmType.SLIDING_WINDOW)
async def heavy():
    return {"data": "x" * 1000, "algorithm": "sliding_window"}


@app.get("/api/free")
async def free():
    return {"data": "no-limit"}


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
        "requests_per_second": round(stats["total_requests"] / max(1, uptime), 1),
        "endpoints": dict(stats["requests"]),
    }


@app.get("/stats/html", response_class=HTMLResponse)
async def get_stats_html():
    uptime = time.monotonic() - stats["start_time"]
    rps = stats["total_requests"] / max(1, uptime)

    rows = ""
    for name, data in stats["requests"].items():
        avg_time = data["total_time"] / max(1, data["count"])
        rows += f"""
        <tr>
            <td>{name}</td>
            <td>{data['count']:,}</td>
            <td>{data['errors']:,}</td>
            <td>{data['count'] - data['errors']:,}</td>
            <td>{avg_time:.1f}ms</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>drogue Benchmark Stats</title>
    <meta http-equiv="refresh" content="2">
    <style>
        body {{ font-family: monospace; margin: 40px; background: #1a1a1a; color: #0f0; }}
        h1 {{ color: #0f0; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #333; padding: 8px 12px; text-align: left; }}
        th {{ background: #222; }}
        .stat {{ margin: 10px 0; }}
        .label {{ color: #888; }}
        .value {{ color: #0f0; font-size: 1.2em; }}
    </style>
</head>
<body>
    <h1>drogue Benchmark Stats</h1>
    <div class="stat"><span class="label">Uptime:</span> <span class="value">{uptime:.0f}s</span></div>
    <div class="stat"><span class="label">Total Requests:</span> <span class="value">{stats['total_requests']:,}</span></div>
    <div class="stat"><span class="label">Total Errors:</span> <span class="value">{stats['total_errors']:,}</span></div>
    <div class="stat"><span class="label">Requests/sec:</span> <span class="value">{rps:.1f}</span></div>
    <div class="stat"><span class="label">Error Rate:</span> <span class="value">{(stats['total_errors']/max(1,stats['total_requests'])*100):.1f}%</span></div>
    <table>
        <tr>
            <th>Endpoint</th>
            <th>Requests</th>
            <th>Errors (429)</th>
            <th>Successful</th>
            <th>Avg Time</th>
        </tr>
        {rows}
    </table>
    <p style="color: #666; margin-top: 20px;">Auto-refreshes every 2 seconds</p>
</body>
</html>"""
