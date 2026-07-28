"""Django example URL configuration."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.root, name="root"),
    path("api/data", views.get_data, name="get_data"),
    path("api/expensive", views.expensive_operation, name="expensive"),
    path("health", views.health, name="health"),
]
