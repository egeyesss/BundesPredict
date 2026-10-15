import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LeagueMark } from "./LeagueMark";

describe("LeagueMark", () => {
  it("renders the official wordmark with an accessible name", () => {
    render(<LeagueMark placement="matchday-header" />);
    expect(screen.getByRole("img", { name: "Bundesliga" })).toHaveAttribute(
      "src",
      "/crests/league/bundesliga.svg",
    );
  });

  it("defaults to 24px tall and accepts 32px", () => {
    const { rerender } = render(<LeagueMark placement="footer" />);
    expect(screen.getByRole("img", { name: "Bundesliga" })).toHaveAttribute("height", "24");
    rerender(<LeagueMark placement="footer" size={32} />);
    expect(screen.getByRole("img", { name: "Bundesliga" })).toHaveAttribute("height", "32");
  });

  it("records where it is used", () => {
    render(<LeagueMark placement="coverage" />);
    expect(screen.getByTestId("league-mark")).toHaveAttribute("data-placement", "coverage");
  });

  it("is never recoloured, rotated or cropped", () => {
    render(<LeagueMark placement="footer" />);
    const mark = screen.getByTestId("league-mark");
    const img = screen.getByRole("img", { name: "Bundesliga" });
    for (const element of [mark, img]) {
      expect(element.className).not.toMatch(/invert|hue|grayscale|brightness|opacity|rotate|animate|overflow-hidden/);
    }
  });

  it("only compiles for the allowed placements and sizes", () => {
    // @ts-expect-error the wordmark lockup must never carry the league logo
    render(<LeagueMark placement="nav" />);
    // @ts-expect-error only 24 and 32px tall
    render(<LeagueMark placement="footer" size={96} />);
  });
});
