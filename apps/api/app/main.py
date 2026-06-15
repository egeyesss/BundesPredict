"""FastAPI entrypoint.

For now just a health check and CORS so the frontend can reach the API. The
prediction endpoints and chat streaming come later.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bundespredict import __version__

app = FastAPI(title="BundesPredict API", version=__version__)

# Dev-friendly CORS. Tighten to the deployed web origin before going public.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Health(BaseModel):
    status: str
    service: str
    version: str


@app.get("/health", response_model=Health)
def health() -> Health:
    """Liveness probe used by docker-compose and CI."""
    return Health(status="ok", service="bundespredict-api", version=__version__)
