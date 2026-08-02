"""Django test views using drogue — proper integration pattern."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from django.http import HttpRequest, JsonResponse

from drogue.adapters.django.limiter import DrogueRateLimiter
from drogue.core.rules.rule import AlgorithmType
from drogue.core.storage.memory import MemoryStorage

_storage = MemoryStorage()
_limiter = DrogueRateLimiter(storage=_storage, default_limits=["100/minute"])


def ping(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


ping = _limiter.limit("10/minute")(ping)


def slow_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


slow_view = _limiter.limit("5/minute", algorithm=AlgorithmType.SLIDING_WINDOW)(slow_view)


def fixed_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


fixed_view = _limiter.limit("5/minute", algorithm=AlgorithmType.FIXED_WINDOW)(fixed_view)


def free(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})
