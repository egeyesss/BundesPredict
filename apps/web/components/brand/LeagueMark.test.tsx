import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LeagueMark } from "./LeagueMark";

describe("LeagueMark", () => {
  it("renders the official logo with an accessible name", () => {
    render(<LeagueMark placement="matchday-header" />);
    expect(screen.getByRole("img", { name: "Bundesliga" })).toHaveAttribute(
      "src",
      "/crests/league/bundesliga.svg",
    );
  });

  // The logo is square with the word under the emblem; below 48px that word stops being readable.
  it("is square, 48px by default and 64px when asked", () => {
    const { rerender } = render(<LeagueMark placement="footer" />);
    const img = () => screen.getByRole("img", { name: "Bundesliga" });
    expect(img()).toHaveAttribute("height", "48");
    expect(img()).toHaveAttribute("width", "48");
    rerender(<LeagueMark placement="footer" size={64} />);
    expect(img()).toHaveAttribute("height", "64");
    expect(img()).toHaveAttribute("width", "64");
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
    // @ts-expect-error only 48 and 64px tall
    render(<LeagueMark placement="footer" size={32} />);
  });
});
