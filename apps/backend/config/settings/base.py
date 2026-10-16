from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env()
# Only the backend's own .env is read. The repo-root .env belongs to the FastAPI app and
# may point at a production database.
env.read_env(BASE_DIR / ".env")

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
THIRD_PARTY_APPS = [
    "rest_framework",
    "drf_spectacular",
]
LOCAL_APPS = [
    "football",
    "predictions",
    "accounts",
    "chat",
    "billing",
    "track_record",
    "notifications",
    "ops",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "config.middleware.proxy_secret_middleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Neon closes idle connections, so keep them short-lived and ping before reuse. The
# pooled Neon URL runs through PgBouncer, which does not support server-side cursors.
DATABASE_CONNECTION_OPTIONS = {
    "CONN_MAX_AGE": 30,
    "CONN_HEALTH_CHECKS": True,
    "DISABLE_SERVER_SIDE_CURSORS": True,
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True

STATIC_URL = "static/"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "EXCEPTION_HANDLER": "config.api.exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "BundesPredict API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {"PeriodKindEnum": "track_record.serializers.PERIOD_KINDS"},
}

# --- accounts: django-allauth headless + django-anymail ---------------------------------------
INSTALLED_APPS += [
    "allauth",
    "allauth.account",
    "allauth.headless",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "anymail",
]
MIDDLEWARE += ["allauth.account.middleware.AccountMiddleware"]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Sign-in is Google or an emailed code; nobody sets a password. A new address signs up with its
# email alone and proves it with the verification code, an existing one asks for a login code.
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
ACCOUNT_LOGIN_BY_CODE_ENABLED = True

HEADLESS_ONLY = True
HEADLESS_CLIENTS = ("browser",)
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": "/login?key={key}",
    "account_signup": "/login",
    "socialaccount_login_error": "/login?error=social",
}

# Google verifies addresses, so a Google sign-in joins the account that already owns the email.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": [
            {
                "client_id": env.str("GOOGLE_CLIENT_ID", default=""),
                "secret": env.str("GOOGLE_CLIENT_SECRET", default=""),
            }
        ],
        "SCOPE": ["profile", "email"],
    }
}

# Resend only delivers from the production settings module; dev prints mail to the console and
# the test runner swaps in the in-memory backend.
RESEND_API_KEY = env.str("RESEND_API_KEY", default="")
if RESEND_API_KEY and env.str("DJANGO_SETTINGS_MODULE", default="").endswith(".prod"):
    MAILERS = {
        "default": {
            "BACKEND": "anymail.backends.resend.EmailBackend",
            "OPTIONS": {"api_key": RESEND_API_KEY},
        }
    }
else:
    MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}
DEFAULT_FROM_EMAIL = env.str("EMAIL_FROM", default="BundesPredict <noreply@example.com>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# --- end accounts block ------------------------------------------------------------------------
