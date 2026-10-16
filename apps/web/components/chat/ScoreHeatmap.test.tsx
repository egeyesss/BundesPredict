import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fixtureDetails } from "@/lib/api/mocks/data";

import { ScoreHeatmap } from "./ScoreHeatmap";

const markets = fixtureDetails["803"].markets;

function renderHeatmap(props: Partial<React.ComponentProps<typeof ScoreHeatmap>> = {}) {
  return render(<ScoreHeatmap home="Dortmund" away="Hoffenheim" markets={markets} {...props} />);
}

describe("ScoreHeatmap", () => {
  it("summarises the most likely scoreline for screen readers", () => {
    renderHeatmap();
    const top = markets.top_scores[0];
    expect(screen.getByRole("img", { name: new RegExp(`Scoreline probabilities, most likely ${top.home}–${top.away} at ${(top.p * 100).toFixed(1)}%`) })).toBeInTheDocument();
  });

  it("draws a 6 by 6 grid and rings the most likely cell", () => {
    const { container } = renderHeatmap();
    expect(container.querySelectorAll("[data-cell]")).toHaveLength(36);
    const top = markets.top_scores[0];
    expect(container.querySelector("[data-top]")).toHaveAttribute("data-score", `${top.home}-${top.away}`);
  });

  it("labels only the cells above 5 percent", () => {
    const { container } = renderHeatmap();
    const cells = [...container.querySelectorAll<HTMLElement>("[data-cell]")];
    for (const cell of cells) {
      const probability = Number(cell.dataset.probability);
      expect(cell.textContent !== "").toBe(probability >= 0.05);
    }
  });

  it("offers every number as a table", async () => {
    renderHeatmap();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Table" }));
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(7);
    expect(screen.getByRole("button", { name: "Hide table" })).toBeInTheDocument();
  });

  it("carries the other view's probability on each cell for the hover tip", () => {
    const { container } = renderHeatmap({ other: { label: "model only", markets: { ...markets, score_grid: markets.score_grid.map((row) => row.map(() => 0.01)) } } });
    expect(container.querySelector("[data-cell]")?.getAttribute("data-compare")).toBe("1.0");
  });
});
