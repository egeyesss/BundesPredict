import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DemoBanner, formatCountdown } from "./DemoBanner";

describe("formatCountdown", () => {
  it("prints hours, minutes and seconds with leading zeros", () => {
    expect(formatCountdown(24 * 3600e3)).toBe("24:00:00");
    expect(formatCountdown(23 * 3600e3 + 41 * 60e3 + 9e3)).toBe("23:41:09");
    expect(formatCountdown(999)).toBe("00:00:00");
  });

  it("never goes negative", () => {
    expect(formatCountdown(-5000)).toBe("00:00:00");
  });
});

describe("DemoBanner", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval", "setTimeout", "clearTimeout"] });
    vi.setSystemTime(new Date("2026-10-26T12:00:00Z"));
  });
  afterEach(() => {
    vi.useRealTimers();
    document.documentElement.style.removeProperty("--demo-bar-h");
  });

  it("says nothing is charged and counts down to the deletion", () => {
    render(<DemoBanner expiresAt="2026-10-27T11:30:00Z" onRestartTour={() => {}} />);
    expect(screen.getByText(/payments use Stripe test cards, nothing is charged/i)).toBeInTheDocument();
    expect(screen.getByRole("timer")).toHaveTextContent("23:30:00");
    act(() => {
      vi.advanceTimersByTime(65_000);
    });
    expect(screen.getByRole("timer")).toHaveTextContent("23:28:55");
  });

  it("shows that the demo has ended once the time is up", () => {
    render(<DemoBanner expiresAt="2026-10-26T11:59:00Z" onRestartTour={() => {}} />);
    expect(screen.queryByRole("timer")).not.toBeInTheDocument();
    expect(screen.getByText(/this demo has ended/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Start a new demo" })).toHaveAttribute("href", "/demo");
  });

  it("copes with a missing expiry", () => {
    render(<DemoBanner expiresAt={null} onRestartTour={() => {}} />);
    expect(screen.queryByRole("timer")).not.toBeInTheDocument();
    expect(screen.getByText(/nothing is charged/i)).toBeInTheDocument();
  });

  it("restarts the tour from the question mark", async () => {
    vi.useRealTimers();
    const onRestartTour = vi.fn();
    render(<DemoBanner expiresAt="2099-01-01T00:00:00Z" onRestartTour={onRestartTour} />);
    await userEvent.click(screen.getByRole("button", { name: "Restart the tour" }));
    expect(onRestartTour).toHaveBeenCalledOnce();
  });

  it("publishes its height so the island and pages can sit below it", () => {
    Object.defineProperty(HTMLElement.prototype, "offsetHeight", { configurable: true, get: () => 44 });
    const { unmount } = render(<DemoBanner expiresAt="2099-01-01T00:00:00Z" onRestartTour={() => {}} />);
    expect(document.documentElement.style.getPropertyValue("--demo-bar-h")).toBe("44px");
    unmount();
    expect(document.documentElement.style.getPropertyValue("--demo-bar-h")).toBe("");
    Reflect.deleteProperty(HTMLElement.prototype, "offsetHeight");
  });
});
