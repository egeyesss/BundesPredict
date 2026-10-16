import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";

import { AdjustmentChip, targetLabel, type AppliedAdjustment } from "./AdjustmentChip";

const clamped: AppliedAdjustment = {
  factor: "player_out",
  team: "home",
  target: "home_attack",
  requested_magnitude_xg: -0.85,
  effective_magnitude_xg: -0.6,
  confidence: "high",
  rationale: "Harry Kane ruled out (knee). Bayern's top scorer.",
};

const plain: AppliedAdjustment = {
  factor: "weather_rain",
  team: null,
  target: "home_attack",
  requested_magnitude_xg: -0.35,
  effective_magnitude_xg: -0.35,
  confidence: "med",
  rationale: "Heavy rain forecast in Munich at kickoff.",
};

const renderChip = (adjustment: AppliedAdjustment, names = { homeName: "Bayern", awayName: "Leipzig" }) =>
  render(
    <TooltipProvider>
      <AdjustmentChip adjustment={adjustment} {...names} />
    </TooltipProvider>,
  );

describe("targetLabel", () => {
  it.each([
    ["home_attack", "Bayern attack"],
    ["away_defense", "Leipzig defense"],
    ["home_adv", "home advantage"],
    ["cards_rate", "cards rate"],
    ["pen_rate", "penalty rate"],
  ])("labels %s as %s", (target, label) => {
    expect(targetLabel(target, "Bayern", "Leipzig")).toBe(label);
  });

  it("falls back to home and away without names", () => {
    expect(targetLabel("home_attack")).toBe("home attack");
  });

  it("keeps an unknown target readable", () => {
    expect(targetLabel("referee_bias")).toBe("referee bias");
  });
});

describe("AdjustmentChip", () => {
  it("shows the factor and the affected side", () => {
    renderChip(clamped);
    expect(screen.getByText("player_out · Bayern attack")).toBeInTheDocument();
  });

  it("shows the asked and the capped magnitude when they differ", () => {
    renderChip(clamped);
    expect(screen.getByText(/asked −0\.85 xG/)).toBeInTheDocument();
    expect(screen.getByText("capped at −0.60")).toBeInTheDocument();
    expect(screen.getByText(/confidence high/)).toBeInTheDocument();
  });

  it("shows a single magnitude when nothing was capped", () => {
    renderChip(plain);
    expect(screen.getByText(/−0\.35 xG/)).toBeInTheDocument();
    expect(screen.queryByText(/capped/)).toBeNull();
    expect(screen.queryByText(/asked/)).toBeNull();
  });

  it("spells out medium confidence", () => {
    renderChip(plain);
    expect(screen.getByText(/confidence medium/)).toBeInTheDocument();
  });

  it("keeps the rationale available to screen readers", () => {
    renderChip(clamped);
    expect(screen.getByText(clamped.rationale, { selector: ".sr-only" })).toBeInTheDocument();
  });

  it("shows the rationale in a tooltip on focus", async () => {
    renderChip(clamped);
    await userEvent.tab();
    const tips = await screen.findAllByText(clamped.rationale);
    expect(tips.length).toBeGreaterThan(1);
  });

  it("treats a request within rounding of the cap as not capped", () => {
    renderChip({ ...plain, requested_magnitude_xg: -0.350001 });
    expect(screen.queryByText(/capped/)).toBeNull();
  });
});
