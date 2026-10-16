import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import type { AgentEvent } from "@/lib/agent-state";
import { teams } from "@/lib/api/mocks/data";
import { recordedStreams } from "@/lib/api/mocks/streams";
import { INITIAL_TRANSCRIPT, transcriptReducer, type AssistantTurn as Turn, type TranscriptAction } from "@/lib/chat/transcript";

import { AssistantTurn } from "./AssistantTurn";

function turnAfter(...actions: TranscriptAction[]): Turn {
  const transcript = actions.reduce(transcriptReducer, INITIAL_TRANSCRIPT);
  return transcript.at(-1) as Turn;
}

const send: TranscriptAction = { type: "send", id: "t1", text: "Guirassy is out" };
const events = (stream: unknown) => (stream as AgentEvent[]).map((event): TranscriptAction => ({ type: "agent", event }));

function renderTurn(turn: Turn, props: Partial<React.ComponentProps<typeof AssistantTurn>> = {}) {
  return render(
    <TooltipProvider>
      <AssistantTurn turn={turn} teams={teams} onWritten={() => {}} onRetry={() => {}} {...props} />
    </TooltipProvider>,
  );
}

describe("a working answer", () => {
  it("shows the orb thinking and the caption", () => {
    renderTurn(turnAfter(send));
    expect(document.querySelector("[data-orb]")).toHaveAttribute("data-orb-state", "thinking");
    expect(screen.getByText("Reading the question")).toBeInTheDocument();
  });

  it("lists the agent steps open while the agent works", () => {
    renderTurn(turnAfter(send, ...events(recordedStreams.happy).slice(0, 4)));
    expect(screen.getByText(/agent steps?/).closest("details")).toHaveAttribute("open");
    expect(screen.getByText(/Dortmund 61%, draw 23%, Hoffenheim 16%/)).toBeInTheDocument();
  });
});

describe("a finished answer", () => {
  const done = () => turnAfter(send, ...events(recordedStreams.happy), { type: "written" });

  it("folds the steps into a summary and shows the explanation and the result card", () => {
    renderTurn(done());
    expect(screen.getByText("3 agent steps").closest("details")).not.toHaveAttribute("open");
    expect(screen.getByText(/The base model has Dortmund at 61%/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Updated odds" })).toBeInTheDocument();
  });

  it("shows a saved answer without stages and without typing", () => {
    const saved: Turn = { ...done(), animate: false, agent: { orb: { phase: "idle" }, calls: 0, stages: [] } };
    renderTurn(saved);
    expect(screen.queryByText(/agent steps?/)).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Updated odds" })).toBeInTheDocument();
  });
});

describe("typing the explanation", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("holds the result card back until the text is written, then reports it", () => {
    const onWritten = vi.fn();
    const writing = turnAfter(send, ...events(recordedStreams.happy));
    renderTurn(writing, { onWritten });
    expect(writing.phase).toBe("writing");
    expect(screen.queryByRole("region", { name: "Updated odds" })).not.toBeInTheDocument();
    expect(document.querySelector(".caret")).toBeInTheDocument();
    expect(onWritten).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(10_000));
    expect(onWritten).toHaveBeenCalledTimes(1);
    expect(document.querySelector(".caret")).not.toBeInTheDocument();
  });

  it("gives screen readers the whole explanation once instead of every character", () => {
    renderTurn(turnAfter(send, ...events(recordedStreams.happy)));
    const full = screen.getByText(/The base model has Dortmund at 61%.*The rest of the squad is unchanged\./);
    expect(full).toHaveClass("sr-only");
  });
});

describe("failures", () => {
  it("shows the server's message and resends the same question on Try again", async () => {
    const onRetry = vi.fn();
    const failed = turnAfter(send, ...events(recordedStreams.error));
    renderTurn(failed, { onRetry });
    expect(screen.getByText("The prediction could not be completed. Try again.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledWith("Guirassy is out");
  });

  it("explains a cut-off answer and offers to ask again", () => {
    const cut = turnAfter(send, ...events((recordedStreams.happy as AgentEvent[]).slice(0, 5)), {
      type: "cut",
      message: "The answer was cut off by a lost connection.",
    });
    renderTurn(cut);
    expect(screen.getByText("The answer was cut off by a lost connection.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask again" })).toBeInTheDocument();
  });
});
