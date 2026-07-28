"""Abuse protection for the prediction endpoints.

Every `/predict` call runs the agent loop, which costs Anthropic tokens, so an
open endpoint is an open wallet. Two layers guard it:

1. **Proxy secret.** The browser talks to the Next.js app, which forwards to
   this API with a shared secret. Without the secret the request is rejected,
   so publishing the API's URL isn't enough to drive it.
2. **Per-client rate limit.** Because every request now arrives *from* the
   proxy, `request.client.host` is the proxy for all of them and is useless as
   a limit key. The proxy forwards the real client address in a header
   instead. That header is only trustworthy because of layer 1 -- nothing
   without the secret can reach us to forge it.

Counters live in process memory: one Railway instance, and a limit that resets
on redeploy is an acceptable trade for not running Redis.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import get_settings

logger = logging.getLogger(__name__)

# Set by the web proxy. Names are lowercased by Starlette on lookup.
CLIENT_IP_HEADER = "x-client-ip"
PROXY_SECRET_HEADER = "x-proxy-secret"

PREDICT_RATE_LIMIT = "10/hour"


def client_key(request: Request) -> str:
    """Rate-limit key: the real caller, not the proxy that relayed them."""
    forwarded = request.headers.get(CLIENT_IP_HEADER)
    if forwarded:
        return forwarded.strip()
    # Direct hit (local dev, or the secret isn't configured yet).
    return get_remote_address(request)


limiter = Limiter(key_func=client_key)


def verify_proxy(request: Request) -> None:
    """Reject anything that didn't come through the web proxy.

    A missing `proxy_secret` disables the check so `docker compose up` and the
    tests work unconfigured. That means forgetting to set it in production
    leaves the endpoint open, so say so loudly at startup rather than failing
    silently open.
    """
    expected = get_settings().proxy_secret
    if not expected:
        return
    supplied = request.headers.get(PROXY_SECRET_HEADER)
    # Constant-time: a plain `==` leaks the secret's prefix through timing.
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="direct access is not allowed")


def warn_if_unprotected() -> None:
    """Log at startup when the proxy secret is missing."""
    if not get_settings().proxy_secret:
        logger.warning(
            "PROXY_SECRET is not set: /predict is reachable by anyone who knows "
            "this API's URL, and the rate limit keys on the caller's own address."
        )
