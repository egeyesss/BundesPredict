"""The Anthropic client and model name the agent runs with, read from the environment."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import cast

import anthropic

from bundespredict.agent.loop import DEV_MODEL, LLMClient
from config.api import ModelUnavailable


@lru_cache
def _client_for(api_key: str) -> LLMClient:
    # The SDK client satisfies the loop's minimal LLMClient surface at runtime; its overloaded
    # signature does not match the protocol structurally, hence the cast.
    return cast(LLMClient, anthropic.Anthropic(api_key=api_key))


def get_llm_client() -> LLMClient:
    """The shared Anthropic client, or a 503 when no API key is configured."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ModelUnavailable("The agent is unavailable: ANTHROPIC_API_KEY is not configured.")
    return _client_for(api_key)


def agent_model() -> str:
    """Haiku unless `AGENT_MODEL` names the production model, as in the FastAPI app."""
    return os.environ.get("AGENT_MODEL") or DEV_MODEL
