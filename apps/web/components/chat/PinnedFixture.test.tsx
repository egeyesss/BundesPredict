import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fixtureDetails, sampleConversation } from "@/lib/api/mocks/data";
import type { PredictResponse } from "@/lib/api/types";
import { ApiFailure } from "@/lib/api/use-resource";

import { PinnedFixture } from "./PinnedFixture";

const fixture = fixtureDetails["803"];
const news = (sampleConversation.messages[1].prediction as PredictResponse).adjusted!;
const noop = () => {};

function pinned(props: Partial<React.ComponentProps<typeof PinnedFixture>> = {}) {
  return render(<PinnedFixture fixture={{ status: "ready", data: fixture }} news={null} orb={{ phase: "idle" }} onOpenHistory={noop} {...props} />);
}

describe("PinnedFixture", () => {
  it("names the match and labels the odds as the model's", () => {
    pinned();
    const region = screen.getByRole("region", { name: "Pinned fixture" });
    expect(within(region).getByText("Dortmund")).toBeInTheDocument();
    expect(within(region).getByText("Hoffenheim")).toBeInTheDocument();
    expect(within(region).getByText("Model")).toBeInTheDocument();
    expect(within(region).queryByRole("button", { name: /odds/ })).not.toBeInTheDocument();
  });

  it("switches to the odds with the user's news and lets them go back to the original", async () => {
    pinned({ news });
    const region = screen.getByRole("region", { name: "Pinned fixture" });
    expect(within(region).getByText("With your news")).toBeInTheDocument();
    await userEvent.click(within(region).getByRole("button", { name: "Show original odds" }));
    expect(within(region).getByText("Original model")).toBeInTheDocument();
    await userEvent.click(within(region).getByRole("button", { name: "Show odds with your news" }));
    expect(within(region).getByText("With your news")).toBeInTheDocument();
  });

  it("moves the bar's numbers with the label", async () => {
    pinned({ news });
    const bar = () => screen.getByRole("img", { name: /^Dortmund \d+%, draw/ }).getAttribute("aria-label");
    const withNews = bar();
    await userEvent.click(screen.getByRole("button", { name: "Show original odds" }));
    expect(bar()).not.toBe(withNews);
  });

  it("points a chat with no fixture to the matchday page", () => {
    pinned({ fixture: { status: "idle" } });
    expect(screen.getByRole("link", { name: "Pick a fixture" })).toHaveAttribute("href", "/matchday");
  });

  it("shows a skeleton while the fixture loads and says what broke when it fails", () => {
    const { rerender } = pinned({ fixture: { status: "loading" } });
    expect(screen.getByRole("region", { name: "Pinned fixture" })).toHaveAttribute("aria-busy", "true");
    rerender(
      <PinnedFixture
        fixture={{ status: "error", failure: new ApiFailure(404, "not_found", "Not found.") }}
        news={null}
        orb={{ phase: "idle" }}
        onOpenHistory={noop}
      />,
    );
    expect(screen.getByText("Couldn't load this fixture")).toBeInTheDocument();
  });

  it("opens the history from the History button", async () => {
    let opened = 0;
    pinned({ onOpenHistory: () => (opened += 1) });
    await userEvent.click(screen.getByRole("button", { name: "History" }));
    expect(opened).toBe(1);
  });
});
