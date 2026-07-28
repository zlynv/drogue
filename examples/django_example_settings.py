"""Django example settings for drogue rate limiting."""

from drogue.adapters.django import DrogueRateLimiter
from drogue.core.config import DrogueConfig

# Configure drogue limiter
DROGUE_CONFIG = DrogueConfig(
    ban_enabled=True,
    ban_threshold=5,
    ddos_enabled=True,
    circuit_breaker_enabled=True,
    metrics_enabled=True,
)

DROGUE_LIMITER = DrogueRateLimiter(
    config=DROGUE_CONFIG,
    default_limits=["100/minute"],
)

# Add to MIDDLEWARE
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Add drogue middleware for global rate limiting
    "drogue.django.middleware.DrogueMiddleware",
]

ROOT_URLCONF = "example_django.urls"
