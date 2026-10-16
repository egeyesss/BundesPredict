import sentry_sdk
from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber

from .base import *  # noqa: F403
from .base import BASE_DIR, DATABASE_CONNECTION_OPTIONS, MIDDLEWARE, env

DEBUG = False
SECRET_KEY = env.str("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
PROXY_SECRET = env.str("PROXY_SECRET")
CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS", default=["https://bundespredict.egeyesilyurt.ca"]
)

DATABASES = {"default": {**env.db("DATABASE_URL"), **DATABASE_CONNECTION_OPTIONS}}

# Railway terminates TLS, and the Vercel rewrite forwards the public host so allauth builds its
# Google redirect_uri on the web origin instead of the Railway one.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False

MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

SENTRY_DSN_BACKEND = env.str("SENTRY_DSN_BACKEND", default="")
if SENTRY_DSN_BACKEND:
    sentry_sdk.init(
        dsn=SENTRY_DSN_BACKEND,
        send_default_pii=False,
        # The shared secret and the caller's address arrive as headers on every request.
        event_scrubber=EventScrubber(
            denylist=[*DEFAULT_DENYLIST, "x-proxy-secret", "x_proxy_secret", "x-client-ip"]
        ),
    )
