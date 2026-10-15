import os

# Points at the db service in infra/docker-compose.yml (host port 5433).
os.environ.setdefault(
    "DATABASE_URL", "postgresql://bundespredict:bundespredict@localhost:5433/bundespredict"
)

from .base import *  # noqa: E402, F403
from .base import DATABASE_CONNECTION_OPTIONS, env  # noqa: E402

DEBUG = True
SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="dev-only-insecure-key")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"])

DATABASES = {"default": {**env.db("DATABASE_URL"), **DATABASE_CONNECTION_OPTIONS}}

# The web dev server sends this value in `x-proxy-secret`: set PROXY_SECRET to the same string
# in apps/web/.env.local (or leave both unset and use this default).
PROXY_SECRET = env.str("PROXY_SECRET", default="dev-only-proxy-secret")
