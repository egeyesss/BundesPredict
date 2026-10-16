import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import { sampleConversation, teams } from "@/lib/api/mocks/data";
import type { PredictResponse } from "@/lib/api/types";

import { ResultCard } from "./ResultCard";

const result = sampleConversation.messages[1].prediction as PredictResponse;

function renderCard(prediction: PredictResponse = result) {
  return render(
    <TooltipProvider>
      <ResultCard result={prediction} teams={teams} />
    </TooltipProvider>,
  );
}

describe("ResultCard with news applied", () => {
  it("shows the model bar, the bar with the news, and the change per outcome", () => {
    renderCard();
    const card = screen.getByRole("region", { name: "Updated odds" });
    expect(within(card).getAllByText("Model only").length).toBeGreaterThan(0);
    expect(within(card).getAllByText("With your news").length).toBeGreaterThan(0);
    expect(within(card).getAllByTestId("delta")).toHaveLength(3);
  });

  it("lists each adjustment as a chip using the short club names", () => {
    renderCard();
    expect(screen.getByText(/player_out/)).toBeInTheDocument();
    expect(screen.getByText(/Dortmund attack/)).toBeInTheDocument();
  });

  it("opens the markets drawer by default and switches between the two views", async () => {
    renderCard();
    const drawer = screen.getByText("More markets and scorelines").closest("details");
    expect(drawer).toHaveAttribute("open");
    const news = screen.getByRole("button", { name: "With your news" });
    const model = screen.getByRole("button", { name: "Model only" });
    expect(news).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(model);
    expect(model).toHaveAttribute("aria-pressed", "true");
    expect(news).toHaveAttribute("aria-pressed", "false");
  });

  it("compares news against model in the markets table and drops the comparison for the model view", async () => {
    renderCard();
    expect(screen.getByText("Change")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Model only" }));
    expect(screen.queryByText("Change")).not.toBeInTheDocument();
  });

  it("labels both expected-goals pairs and keeps each pair on one line", () => {
    renderCard();
    const line = screen.getByText(/^Expected goals/);
    expect(line.textContent).toMatch(/^Expected goals .+: \d\.\d\d – \d\.\d\d with your news, \d\.\d\d – \d\.\d\d model only$/);
    // Browsers may break right after an en dash, so only nowrap keeps "1.62 –" with "0.92".
    const pairs = within(line).getAllByText(/^\d\.\d\d – \d\.\d\d$/);
    expect(pairs).toHaveLength(2);
    for (const pair of pairs) expect(pair).toHaveClass("whitespace-nowrap");
  });
});

describe("ResultCard without news", () => {
  const plain: PredictResponse = { ...result, adjusted: null, adjustments: [] };

  it("shows only the model odds and no view switch", () => {
    renderCard(plain);
    expect(screen.getByRole("region", { name: "Model odds" })).toBeInTheDocument();
    expect(screen.queryByText("With your news")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Model only" })).not.toBeInTheDocument();
  });

  it("renders nothing when the agent produced no baseline at all", () => {
    const { container } = renderCard({ ...result, baseline: null, adjusted: null });
    expect(container).toBeEmptyDOMElement();
  });
});
