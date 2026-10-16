import { act, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OddsBar } from "./OddsBar";
import { ProbabilityBars } from "./ProbabilityBars";

function stubReducedMotion(reduced: boolean) {
  vi.spyOn(window, "matchMedia").mockImplementation(
    (query) =>
      ({
        matches: reduced && query.includes("prefers-reduced-motion"),
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      }) as unknown as MediaQueryList,
  );
}

const BASELINE = { p_home: 0.6888, p_draw: 0.1664, p_away: 0.1448, exp_home_goals: 2.61, exp_away_goals: 1.14 };
const ADJUSTED = { p_home: 0.5811, p_draw: 0.2424, p_away: 0.1765, exp_home_goals: 1.66, exp_away_goals: 0.79 };

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["requestAnimationFrame", "cancelAnimationFrame"] });
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("OddsBar", () => {
  it("reads out all three outcomes for screen readers", () => {
    render(<OddsBar home="Bayern" away="Dortmund" probs={[0.52, 0.23, 0.25]} expectedGoals={[1.9, 1.1]} />);
    expect(screen.getByRole("img", { name: "Bayern 52%, draw 23%, Dortmund 25%" })).toBeInTheDocument();
  });

  it("prints a text value for every segment", () => {
    const { container } = render(<OddsBar home="Bayern" away="Dortmund" probs={[0.52, 0.23, 0.25]} expectedGoals={[1.9, 1.1]} />);
    expect(container.textContent).toContain("52%");
    expect(container.textContent).toContain("Draw 23%");
    expect(container.textContent).toContain("25%");
  });

  it("sizes segments by the true probabilities and marks the leader", () => {
    const { container } = render(<OddsBar home="Bayern" away="Dortmund" probs={[0.6421, 0.1902, 0.1677]} expectedGoals={[2.6, 1.1]} />);
    const segments = container.querySelectorAll<HTMLElement>("[data-segment]");
    expect([...segments].map((segment) => segment.style.flexGrow)).toEqual(["0.6421", "0.1902", "0.1677"]);
    expect([...segments].map((segment) => segment.dataset.role)).toEqual(["win", "draw", "lose"]);
    expect([...segments].map((segment) => segment.hasAttribute("data-lead"))).toEqual([true, false, false]);
  });

  it("gives red to the less likely team, never by home or away", () => {
    const { container } = render(<OddsBar home="Union" away="Dortmund" probs={[0.2618, 0.2544, 0.4838]} expectedGoals={[1.1, 1.7]} />);
    const roles = [...container.querySelectorAll<HTMLElement>("[data-segment]")].map((segment) => segment.dataset.role);
    expect(roles).toEqual(["lose", "draw", "win"]);
  });

  it("shows tiny values as <1", () => {
    const { container } = render(<OddsBar home="A" away="B" probs={[0.968, 0.028, 0.004]} expectedGoals={[3, 0.4]} />);
    expect(container.textContent).toContain("<1%");
  });
});

describe("ProbabilityBars", () => {
  it("renders only the model bar when there is no adjustment", () => {
    stubReducedMotion(false);
    render(<ProbabilityBars home="Bayern" away="Leipzig" baseline={BASELINE} />);
    expect(screen.getAllByRole("img")).toHaveLength(1);
    expect(screen.queryByText(/pts/)).toBeNull();
  });

  it("shows signed point changes with arrows for each outcome", () => {
    stubReducedMotion(true);
    render(<ProbabilityBars home="Bayern" away="Leipzig" baseline={BASELINE} adjusted={ADJUSTED} />);
    const tiles = screen.getAllByTestId("delta");
    expect(tiles).toHaveLength(3);
    expect(within(tiles[0]).getByText(/▼/)).toHaveTextContent("▼ −10.8 pts");
    expect(within(tiles[1]).getByText(/▲/)).toHaveTextContent("▲ +7.6 pts");
    expect(within(tiles[2]).getByText(/▲/)).toHaveTextContent("▲ +3.2 pts");
  });

  it("starts the adjusted bar at the baseline and tweens to the adjusted values", () => {
    stubReducedMotion(false);
    render(<ProbabilityBars home="Bayern" away="Leipzig" baseline={BASELINE} adjusted={ADJUSTED} />);
    const bars = screen.getAllByRole("img");
    const growths = () => [...bars[1].querySelectorAll<HTMLElement>("[data-segment]")].map((segment) => segment.style.flexGrow);
    expect(growths()).toEqual(["0.6888", "0.1664", "0.1448"]);
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(growths()).toEqual(["0.5811", "0.2424", "0.1765"]);
  });

  it("jumps straight to the adjusted values under reduced motion", () => {
    stubReducedMotion(true);
    render(<ProbabilityBars home="Bayern" away="Leipzig" baseline={BASELINE} adjusted={ADJUSTED} />);
    const bars = screen.getAllByRole("img");
    const growths = [...bars[1].querySelectorAll<HTMLElement>("[data-segment]")].map((segment) => segment.style.flexGrow);
    expect(growths).toEqual(["0.5811", "0.2424", "0.1765"]);
  });

  it("reads expected goals as xG home – away, before and after", () => {
    stubReducedMotion(true);
    const { container } = render(<ProbabilityBars home="Bayern" away="Leipzig" baseline={BASELINE} adjusted={ADJUSTED} />);
    expect(container.textContent).toContain("xG 2.61 – 1.14");
    expect(container.textContent).toContain("1.66 – 0.79");
    expect(container.textContent).not.toContain("λ");
  });

  it("labels the two rows", () => {
    stubReducedMotion(true);
    render(<ProbabilityBars home="Bayern" away="Leipzig" baseline={BASELINE} adjusted={ADJUSTED} />);
    expect(screen.getByText("Model only")).toBeInTheDocument();
    expect(screen.getByText("With your news")).toBeInTheDocument();
  });
});
