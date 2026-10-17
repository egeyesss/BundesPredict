import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { meFor } from "@/lib/api/mocks/data";

vi.mock("@/lib/account/timezone", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/account/timezone")>()),
  browserTimeZone: () => "Europe/Berlin",
}));

import { TimeZoneCard } from "./TimeZoneCard";

describe("TimeZoneCard", () => {
  it("offers the browser zone when the saved one differs", () => {
    render(<TimeZoneCard me={{ ...meFor("free"), timezone: "America/Toronto" }} onSaved={() => {}} />);
    expect(screen.getByRole("button", { name: "Use browser time zone" })).toBeInTheDocument();
  });

  it("stays quiet before any zone has been reported", () => {
    render(<TimeZoneCard me={{ ...meFor("free"), timezone: null }} onSaved={() => {}} />);
    expect(screen.queryByRole("button", { name: "Use browser time zone" })).not.toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Time zone" })).toHaveValue("Europe/Berlin");
  });

  it("stays quiet when the saved zone matches the browser", () => {
    render(<TimeZoneCard me={{ ...meFor("free"), timezone: "Europe/Berlin" }} onSaved={() => {}} />);
    expect(screen.queryByRole("button", { name: "Use browser time zone" })).not.toBeInTheDocument();
  });
});
