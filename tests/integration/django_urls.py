"""Django URL configuration for integration test."""
from django.urls import path

from tests.integration import django_views

urlpatterns = [
    path("api/ping", django_views.ping),
    path("api/slow", django_views.slow_view),
    path("api/fixed", django_views.fixed_view),
    path("api/free", django_views.free),
]
