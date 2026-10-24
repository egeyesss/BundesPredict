import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it } from "vitest";

import { adminMetricsFor } from "@/lib/api/mocks/admin";

import { AdminDashboard } from "./AdminDashboard";

beforeAll(() => {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

describe("AdminDashboard", () => {
  it("shows live and test-mode numbers apart, with the test card labelled", () => {
    render(<AdminDashboard metrics={adminMetricsFor(30, false)} range={30} />);

    const tiles = screen.getByRole("region", { name: "Key numbers" });
    expect(within(tiles).getByText("MRR").parentElement).toHaveTextContent("$0.00");
    expect(screen.getByRole("heading", { name: "No paying subscribers yet" })).toBeInTheDocument();

    const testCard = screen.getByRole("region", { name: "Test-mode subscriptions" });
    expect(within(testCard).getByText("Test mode")).toBeInTheDocument();
    expect(within(testCard).getByText("$30.00")).toBeInTheDocument();
  });

  it("marks the selected range and links to the others", () => {
    render(<AdminDashboard metrics={adminMetricsFor(7, false)} range={7} />);

    expect(screen.getByRole("link", { name: "7 days" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "90 days" })).toHaveAttribute("href", "/admin?days=90");
  });

  it("explains the masked view and shows masked emails only", () => {
    render(<AdminDashboard metrics={adminMetricsFor(30, true)} range={30} />);

    expect(screen.getByText("Read-only demo view.")).toBeInTheDocument();
    expect(screen.getByText("a•••@example.com")).toBeInTheDocument();
    expect(screen.queryByText("a.keller@example.com")).not.toBeInTheDocument();
  });

  it("gives every status an icon-backed label, never colour alone", () => {
    render(<AdminDashboard metrics={adminMetricsFor(30, false)} range={30} />);

    const webhooks = screen.getByRole("table", { name: "Recent Stripe webhook events" });
    expect(within(webhooks).getByText("failed")).toBeInTheDocument();
    expect(within(webhooks).getAllByText("processed").length).toBeGreaterThan(0);
  });

  it("swaps a chart for its table and back", async () => {
    render(<AdminDashboard metrics={adminMetricsFor(7, false)} range={7} />);
    const [chatsToggle] = screen.getAllByRole("button", { name: "Show as table" });

    await userEvent.click(chatsToggle);

    expect(chatsToggle).toHaveTextContent("Hide table");
    expect(screen.getByRole("table", { name: "Chats per day by plan" })).toBeVisible();
    expect(screen.getByRole("img", { name: /Chats per day by plan/, hidden: true })).not.toBeVisible();
  });

  it("flags a Pro user who costs more than they pay", async () => {
    render(<AdminDashboard metrics={adminMetricsFor(30, false)} range={30} />);
    const toggles = screen.getAllByRole("button", { name: "Show as table" });

    await userEvent.click(toggles[1]);

    const table = screen.getByRole("table", { name: "Agent cost per Pro user" });
    expect(within(table).getByText("over the line")).toBeInTheDocument();
  });
});
