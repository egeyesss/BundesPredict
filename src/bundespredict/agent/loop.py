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

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

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


@dataclass(frozen=True)
class AgentEvent:
    """One observable step of a run, so a caller can stream progress.

    ``tool_call`` and ``tool_result`` carry JSON-friendly ``data`` (the tool name
    plus its input or outcome); the terminal ``final`` event carries the
    :class:`AgentResult` instead. Every run ends with exactly one ``final``.
    """

    type: Literal["tool_call", "tool_result", "final"]
    data: dict[str, Any] = field(default_factory=dict)
    result: AgentResult | None = None


def _text_of(response: Any) -> str:
    """Concatenate the text blocks of a model response into one string."""
    parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    return "\n".join(p for p in parts if p).strip()


def run_agent_events(
    query: str,
    service: PredictionService,
    *,
    client: LLMClient,
    model: str = DEV_MODEL,
    max_tokens: int = _MAX_TOKENS,
    max_turns: int = _MAX_TURNS,
) -> Iterator[AgentEvent]:
    """Run the tool-calling loop, yielding an event per observable step.

    This is the streaming seam: the SSE endpoint forwards these events to the
    browser so the user watches the agent work (which tool, with what input,
    did it succeed) instead of staring at a spinner. The loop's behaviour is
    otherwise identical to :func:`run_agent`, which is just a drain of this.
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
            tool_input = dict(block.input)
            yield AgentEvent("tool_call", {"name": block.name, "input": tool_input})
            outcome = dispatch(block.name, tool_input, service)
            yield AgentEvent(
                "tool_result",
                {"name": block.name, "ok": not outcome.is_error, "payload": outcome.payload},
            )
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
    yield AgentEvent(
        "final",
        result=AgentResult(
            query=query,
            explanation=explanation,
            record=service.last_prediction,
            messages=messages,
        ),
    )


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
    result: AgentResult | None = None
    for event in run_agent_events(
        query,
        service,
        client=client,
        model=model,
        max_tokens=max_tokens,
        max_turns=max_turns,
    ):
        if event.type == "final":
            result = event.result
    assert result is not None  # run_agent_events always ends with a final event
    return result
