import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import happy from "@/lib/api/mocks/recorded/streams/happy.json";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { PredictStreamEvent } from "@/lib/api/types";

import { AskDemo } from "./AskDemo";
import { compactDemoStream } from "./demo-replay";

const stream = compactDemoStream(happy as unknown as PredictStreamEvent[]);

describe("AskDemo", () => {
  it("renders the finished answer without running anything", async () => {
    render(
      <TooltipProvider>
        <AskDemo stream={stream} />
      </TooltipProvider>,
    );
    expect(screen.getByText(/Guirassy is out for Dortmund/)).toBeInTheDocument();
    expect(screen.getByText("Answered with 3 steps")).toBeInTheDocument();
    expect(screen.getAllByRole("img", { name: /^Dortmund 61%, draw 23%, Hoffenheim 16%$/ }).length).toBeGreaterThan(0);
    expect(await screen.findByRole("img", { name: /^Dortmund 53%, draw 27%, Hoffenheim 20%$/ })).toBeInTheDocument();
    expect(screen.getByText(/player_out · Dortmund attack/)).toBeInTheDocument();
  });

  it("lists the recorded example as sample data, never as live", () => {
    render(
      <TooltipProvider>
        <AskDemo stream={stream} />
      </TooltipProvider>,
    );
    expect(screen.getByText(/recorded from the real engine/i)).toBeInTheDocument();
  });

  describe("replay", () => {
    beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
    afterEach(() => vi.useRealTimers());

    it("shows the agent working, then the answer, when Replay is pressed", async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(
      <TooltipProvider>
        <AskDemo stream={stream} />
      </TooltipProvider>,
    );
      await user.click(screen.getByRole("button", { name: "Replay" }));

      expect(screen.getByRole("status")).toHaveTextContent("Reading the question");
      expect(screen.queryByRole("img", { name: /^Dortmund 53%/ })).not.toBeInTheDocument();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000);
      });
      expect(screen.getByRole("status")).toHaveTextContent(/Looking up the squad|Running the model|Applying adjustments/);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(8000);
      });
      expect(screen.getByText("Answered with 3 steps")).toBeInTheDocument();
      expect(await screen.findByRole("img", { name: /^Dortmund 53%/ })).toBeInTheDocument();
    });
  });
});
