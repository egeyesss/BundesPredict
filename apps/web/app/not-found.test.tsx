import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import NotFound from "./not-found";

describe("NotFound", () => {
  it("says the page is off the team sheet and links to the matchday and home", () => {
    render(<NotFound />);

    expect(screen.getByRole("heading", { level: 1, name: "That page isn't on the team sheet" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Matchday" })).toHaveAttribute("href", "/matchday");
    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
  });
});
