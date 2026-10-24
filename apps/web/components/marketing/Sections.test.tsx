import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { crestManifest } from "@/lib/brand";

import { Coverage } from "./Coverage";
import { Hero } from "./Hero";
import { HowItWorks } from "./HowItWorks";
import { Pricing } from "./Pricing";

describe("Hero", () => {
  it("has one h1 named after the product and two calls to action", () => {
    render(<Hero />);
    expect(screen.getByRole("heading", { level: 1, name: "BundesPredict" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Try the demo" })).toHaveAttribute("href", "/demo");
    expect(screen.getByRole("link", { name: "Start free" })).toHaveAttribute("href", "/login");
    expect(screen.getByText(/3 free chats a day/)).toBeInTheDocument();
  });

  it("speaks of probabilities and not of betting", () => {
    const { container } = render(<Hero />);
    expect(container.textContent).toMatch(/probabilit/i);
    expect(container.textContent).not.toMatch(/\b(bet|bets|betting|odds on|punt)\b/i);
  });
});

describe("HowItWorks", () => {
  it("covers the model, the agent and the audit trail", () => {
    render(<HowItWorks />);
    for (const tag of ["Model", "Agent", "Audit trail"]) expect(screen.getByText(tag)).toBeInTheDocument();
    expect(screen.getByText("±0.60 xG")).toBeInTheDocument();
  });
});

describe("Coverage", () => {
  it("shows the league mark once and a crest for each club", () => {
    render(<Coverage />);
    expect(screen.getAllByTestId("league-mark")).toHaveLength(1);
    expect(screen.getByTestId("league-mark")).toHaveAttribute("data-placement", "coverage");
    const strip = screen.getByRole("list", { name: "Clubs" });
    expect(within(strip).getAllByRole("listitem")).toHaveLength(Object.keys(crestManifest).length);
  });
});

describe("Pricing", () => {
  it("offers Free at 3 chats a day and Pro at 5 CAD a month for 100", () => {
    render(<Pricing />);
    expect(screen.getByText("3 agent chats a day")).toBeInTheDocument();
    expect(screen.getByText(/100 agent chats a day/)).toBeInTheDocument();
    expect(screen.getByText(/CAD/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Start free" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: "Go Pro" })).toHaveAttribute("href", "/login?next=%2Faccount");
  });
});
