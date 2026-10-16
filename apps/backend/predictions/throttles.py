"""Per-client rate limit for the agent endpoint, kept in the database cache table."""

from __future__ import annotations

from typing import Any

from django.core.cache.backends.db import DatabaseCache
from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle

# Same budget as FastAPI's slowapi limit: every request runs the agent, which costs tokens.
PREDICT_RATE_LIMIT = "10/hour"

THROTTLE_CACHE_TABLE = "predict_throttle_cache"

# Created by predictions/migrations/0003_throttle_cache_table.py, so deploys need no
# `createcachetable` step. The entry cap leaves room for every client of a busy hour.
throttle_cache = DatabaseCache(THROTTLE_CACHE_TABLE, {"OPTIONS": {"MAX_ENTRIES": 10_000}})

CLIENT_IP_META = "HTTP_X_CLIENT_IP"
MAX_IDENT_LENGTH = 64


class PredictThrottle(SimpleRateThrottle):
    """Limits each caller, identified by the address the web proxy forwards.

    Behind the proxy the socket address is the proxy itself, so it is useless as a key. The
    forwarded header is trustworthy because the proxy-secret middleware rejects any request
    that did not come through the proxy before it reaches this class.
    """

    scope = "predict"
    rate = PREDICT_RATE_LIMIT
    cache = throttle_cache

    def get_cache_key(self, request: Request, view: Any) -> str:
        forwarded = request.META.get(CLIENT_IP_META, "").strip()
        ident = forwarded or request.META.get("REMOTE_ADDR", "")
        return self.cache_format % {"scope": self.scope, "ident": ident[:MAX_IDENT_LENGTH]}
