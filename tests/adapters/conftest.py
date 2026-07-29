"""Configure Django once for all adapter tests."""
import django
from django.conf import settings


def pytest_configure() -> None:
    settings.configure(
        INSTALLED_APPS=["django.contrib.contenttypes"],
        MIDDLEWARE=[],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        ROOT_URLCONF="_integration_test.django_urls",
    )
    django.setup()
