"""FastAPI entrypoint.

A health check plus the prediction endpoint (the agent + engine behind HTTP).
Token/tool streaming over SSE comes with the chat UI.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from bundespredict import __version__

from . import predict
from .config import get_settings
from .security import limiter, warn_if_unprotected

app = FastAPI(title="BundesPredict API", version=__version__)

# Allows the local web origin by default; WEB_ORIGIN overrides for deploys.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().web_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

# slowapi reads the limiter off app.state and needs its own 429 handler.
app.state.limiter = limiter
# slowapi types the handler against its own exception; Starlette's signature
# wants a plain Exception, so the narrower type doesn't line up.
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.include_router(predict.router)

warn_if_unprotected()


class Health(BaseModel):
    status: str
    service: str
    version: str


@app.get("/health", response_model=Health)
def health() -> Health:
    """Liveness probe used by docker-compose and CI."""
    return Health(status="ok", service="bundespredict-api", version=__version__)
