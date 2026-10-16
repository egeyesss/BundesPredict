import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { fixtureCards } from "@/lib/api/mocks/data";

import { FixtureCard } from "./FixtureCard";

const bayern = fixtureCards.find((fixture) => fixture.home.code === "FCB")!;

describe("FixtureCard", () => {
  it("names the match, both clubs and the kickoff", () => {
    render(<FixtureCard fixture={bayern} />);
    const card = screen.getByRole("article", { name: "Bayern v Mainz" });
    expect(within(card).getByRole("img", { name: "Bayern Munich" })).toBeInTheDocument();
    expect(within(card).getByRole("img", { name: "1.FSV Mainz 05" })).toBeInTheDocument();
    expect(card.querySelector("time")).toHaveAttribute("datetime", bayern.kickoff_utc);
  });

  it("reads the odds out as one sentence and shows expected goals", () => {
    render(<FixtureCard fixture={bayern} />);
    expect(screen.getByRole("img", { name: /^Bayern \d+(\.\d+)?%, draw \d+(\.\d+)?%, Mainz \d+(\.\d+)?%$/ })).toBeInTheDocument();
    expect(screen.getByRole("article").textContent).toMatch(/xG\s*\d\.\d\d\s*–\s*\d\.\d\d/);
  });

  it("links to a chat pinned to the fixture", () => {
    render(<FixtureCard fixture={bayern} />);
    expect(screen.getByRole("link", { name: "Ask about this match →" })).toHaveAttribute("href", `/chat?fixture=${bayern.id}`);
  });
});
