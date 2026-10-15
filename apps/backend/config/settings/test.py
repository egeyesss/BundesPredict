from .base import *  # noqa: F403
from .base import DATABASE_CONNECTION_OPTIONS

SECRET_KEY = "test-only-insecure-key"
ALLOWED_HOSTS = ["testserver"]

# Host and credentials are filled in by the session fixture in tests/conftest.py once the
# Postgres container is up; DATABASE_URL from the shell is deliberately ignored.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "bundespredict",
        **DATABASE_CONNECTION_OPTIONS,
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
