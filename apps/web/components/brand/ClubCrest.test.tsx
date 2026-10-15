import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ClubCrest } from "./ClubCrest";

const bayern = { name: "Bayern", code: "FCB", crest: "/crests/FCB.svg" };
const newClub = { name: "Neustadt", code: "NEU", crest: null };

describe("ClubCrest", () => {
  it("renders the crest image with the club name as alt text", () => {
    render(<ClubCrest team={bayern} size={32} />);
    const img = screen.getByRole("img", { name: "Bayern" });
    expect(img).toHaveAttribute("src", "/crests/FCB.svg");
    expect(img).toHaveAttribute("width", "32");
    expect(img).toHaveAttribute("height", "32");
  });

  it("falls back to the manifest asset when the team has no crest field", () => {
    render(<ClubCrest team={{ name: "Dortmund", code: "BVB" }} size={20} />);
    expect(screen.getByRole("img", { name: "Dortmund" })).toHaveAttribute(
      "src",
      "/crests/BVB.svg",
    );
  });

  it("shows the kit chip when the API reports no crest", () => {
    render(<ClubCrest team={newClub} size={48} />);
    const chip = screen.getByRole("img", { name: "Neustadt" });
    expect(chip).toHaveAttribute("data-fallback", "chip");
    expect(chip).toHaveTextContent("NEU");
  });

  it("shows the kit chip when the image fails to load", () => {
    render(<ClubCrest team={bayern} size={32} />);
    fireEvent.error(screen.getByRole("img", { name: "Bayern" }));
    const chip = screen.getByRole("img", { name: "Bayern" });
    expect(chip).toHaveAttribute("data-fallback", "chip");
    expect(chip).toHaveTextContent("FCB");
  });

  it("uses only the first letter on the chip at 20px", () => {
    render(<ClubCrest team={newClub} size={20} />);
    expect(screen.getByRole("img", { name: "Neustadt" })).toHaveTextContent(/^N$/);
  });

  it("colours the chip from the club's manifest colours", () => {
    render(<ClubCrest team={{ name: "Dortmund", code: "BVB", crest: null }} size={32} />);
    const chip = screen.getByRole("img", { name: "Dortmund" });
    expect(chip.style.getPropertyValue("--chip-primary")).toBe("#FDE100");
    expect(chip.style.getPropertyValue("--chip-secondary")).toBe("#000000");
  });

  it("applies no visual treatment to dark crests", () => {
    render(<ClubCrest team={{ name: "Gladbach", code: "BMG" }} size={32} />);
    const img = screen.getByRole("img", { name: "Gladbach" });
    expect(img.className).not.toMatch(/invert|bg-white|brightness/);
  });
});
