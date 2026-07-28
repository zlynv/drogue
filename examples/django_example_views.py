"""Django example views for drogue rate limiting."""

from django.http import JsonResponse

from drogue.adapters.django import DrogueRateLimiter

from .example_settings import DROGUE_LIMITER

limiter: DrogueRateLimiter = DROGUE_LIMITER


def root(request):
    """Basic rate-limited view."""
    return JsonResponse({"message": "Hello, World!"})


@limiter.limit("10/minute")
def get_data(request):
    """Rate-limited to 10 requests per minute."""
    return JsonResponse({"data": "value"})


@limiter.limit("3/minute")
def expensive_operation(request):
    """Rate-limited to 3 requests per minute."""
    return JsonResponse({"result": "computed"})


def health(request):
    """No rate limit."""
    return JsonResponse({"status": "ok"})
