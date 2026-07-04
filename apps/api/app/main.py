"""FastAPI entrypoint.

A health check plus the prediction endpoint (the agent + engine behind HTTP).
Token/tool streaming over SSE comes with the chat UI.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bundespredict import __version__

from . import predict
from .config import get_settings

app = FastAPI(title="BundesPredict API", version=__version__)

# Allows the local web origin by default; WEB_ORIGIN overrides for deploys.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().web_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict.router)


class Health(BaseModel):
    status: str
    service: str
    version: str


@app.get("/health", response_model=Health)
def health() -> Health:
    """Liveness probe used by docker-compose and CI."""
    return Health(status="ok", service="bundespredict-api", version=__version__)
