"""The agent tool-calling loop.

A thin, provider-shaped loop: send the conversation to the model, run any tool
calls it makes against the :class:`PredictionService`, feed the results back, and
repeat until the model returns a final text answer. The Anthropic client is
injected rather than constructed here, which keeps the loop pure of network setup
and lets tests drive it with a scripted client (recorded transcripts, no live
API in CI).

The loop itself does no math and no validation beyond shuttling messages; the
guardrails live in :func:`bundespredict.agent.tools.dispatch` and the engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .prompt import build_system_prompt
from .service import PredictionRecord, PredictionService
from .tools import TOOL_SPECS, dispatch

# Haiku for cheap dev iteration; Sonnet for production. Provider is swappable
# behind the injected client.
DEV_MODEL = "claude-haiku-4-5-20251001"
PROD_MODEL = "claude-sonnet-4-6"

_MAX_TOKENS = 1024
# Generous ceiling so a normal baseline -> ground -> adjust -> explain run never
# hits it; it only exists to stop a pathological tool-call loop.
_MAX_TURNS = 8


class _Messages(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class LLMClient(Protocol):
    """Structural type satisfied by ``anthropic.Anthropic`` and the test fake."""

    @property
    def messages(self) -> _Messages: ...


@dataclass(frozen=True)
class AgentResult:
    """What one agent run produced: the served prediction and its explanation."""

    query: str
    explanation: str
    record: PredictionRecord | None
    messages: list[dict[str, Any]] = field(default_factory=list)


def _text_of(response: Any) -> str:
    """Concatenate the text blocks of a model response into one string."""
    parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    return "\n".join(p for p in parts if p).strip()


def run_agent(
    query: str,
    service: PredictionService,
    *,
    client: LLMClient,
    model: str = DEV_MODEL,
    max_tokens: int = _MAX_TOKENS,
    max_turns: int = _MAX_TURNS,
) -> AgentResult:
    """Run the tool-calling loop for one user query.

    Returns the final explanation plus the service's recorded prediction (baseline
    and adjusted). ``record`` is ``None`` only if the model answered without ever
    calling a prediction tool (e.g. a pure clarification), which the caller can
    treat as "nothing to persist".
    """
    system = build_system_prompt(service.teams)
    messages: list[dict[str, Any]] = [{"role": "user", "content": query}]

    response: Any = None
    for _ in range(max_turns):
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=TOOL_SPECS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            break

        tool_results: list[dict[str, Any]] = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            outcome = dispatch(block.name, dict(block.input), service)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": outcome.to_json(),
                    "is_error": outcome.is_error,
                }
            )
        messages.append({"role": "user", "content": tool_results})

    explanation = _text_of(response) if response is not None else ""
    return AgentResult(
        query=query,
        explanation=explanation,
        record=service.last_prediction,
        messages=messages,
    )
