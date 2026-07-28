"""Shared async bridge for sync frameworks (Flask, Django, DRF).

Provides a single `run_async()` function that safely runs async coroutines
from synchronous code, handling both cases:
1. No running event loop (Flask WSGI, Django sync views): uses asyncio.run()
2. Running event loop (Django async views, ASGI wrappers): delegates to a
   background thread with its own event loop
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any

# Shared background loop for async contexts (running event loop detected)
_bg_loop: asyncio.AbstractEventLoop | None = None
_bg_thread: threading.Thread | None = None
_init_lock = threading.Lock()


def _ensure_background_loop() -> asyncio.AbstractEventLoop:
    """Lazily initialize a background event loop running in a daemon thread."""
    global _bg_loop, _bg_thread
    if _bg_loop is not None and _bg_loop.is_running():
        return _bg_loop
    with _init_lock:
        if _bg_loop is not None and _bg_loop.is_running():
            return _bg_loop
        _bg_loop = asyncio.new_event_loop()
        _bg_thread = threading.Thread(
            target=_bg_loop.run_forever, daemon=True, name="drogue-async-bg"
        )
        _bg_thread.start()
        return _bg_loop


def run_async(coro: Any) -> Any:
    """Run an async coroutine from synchronous code.

    Handles both sync-only contexts (Flask/WSGI) and mixed contexts
    (Django async views wrapping sync throttling).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        # No running loop — safe to use asyncio.run()
        return asyncio.run(coro)
    else:
        # Running loop detected — delegate to background thread
        bg_loop = _ensure_background_loop()
        future = asyncio.run_coroutine_threadsafe(coro, bg_loop)
        return future.result()
