import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MatchdayEmpty, MatchdayError, MatchdaySkeleton } from "./MatchdayStates";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

describe("MatchdaySkeleton", () => {
  it("is busy and shaped like the fixture grid", () => {
    render(<MatchdaySkeleton />);
    expect(screen.getByRole("status", { name: "Loading fixtures" })).toHaveAttribute("aria-busy", "true");
    expect(document.querySelectorAll('[data-slot="skeleton-card"]')).toHaveLength(6);
  });
});

describe("MatchdayEmpty", () => {
  it("explains the pause and points at the last results", () => {
    render(<MatchdayEmpty />);
    expect(screen.getByRole("heading", { name: "No Bundesliga matches this week" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See last matchday's results" })).toHaveAttribute("href", "/track-record");
  });
});

describe("MatchdayError", () => {
  it("says what broke and refetches on Retry", async () => {
    render(<MatchdayError />);
    expect(screen.getByRole("heading", { name: "Couldn't load this week's fixtures" })).toBeInTheDocument();
    expect(screen.getByText("The connection to our server failed. Your chats and account are fine.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refresh).toHaveBeenCalledOnce();
  });
});
