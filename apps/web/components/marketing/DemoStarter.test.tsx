import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw/http";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SessionProvider } from "@/components/account/SessionProvider";
import { meFor } from "@/lib/api/mocks/data";
import { server } from "@/lib/api/mocks/node";
import { setMockSession } from "@/lib/api/mocks/session";
import { setupApiMocks } from "@/lib/api/mocks/vitest";

const navigate = vi.hoisted(() => vi.fn());
vi.mock("@/lib/navigate", () => ({ navigate }));

import { DemoStarter } from "./DemoStarter";

setupApiMocks();

beforeEach(() => navigate.mockReset());

const mount = () =>
  render(
    <SessionProvider>
      <DemoStarter />
    </SessionProvider>,
  );

function countStarts() {
  const calls = { count: 0 };
  server.use(
    http.post("*/api/v1/demo/start", () => {
      calls.count += 1;
      return HttpResponse.json(meFor("demo"), { status: 201 });
    }),
  );
  return calls;
}

describe("DemoStarter when signed out", () => {
  it("creates the demo account once and opens the matchday", async () => {
    const starts = countStarts();
    mount();
    expect(screen.getByRole("status")).toHaveTextContent(/setting up your demo/i);
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/matchday"));
    expect(starts.count).toBe(1);
  });

  it("sends the CSRF token Django set when the page asked who is signed in", async () => {
    let header: string | null = null;
    server.use(
      http.post("*/api/v1/demo/start", ({ request }) => {
        header = request.headers.get("X-CSRFToken");
        return HttpResponse.json(meFor("demo"), { status: 201 });
      }),
    );
    mount();
    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(header).toBe("mock-csrf-token");
  });

  it.each([
    ["demo_ip_limit", "Too many demos from this network today", "This network has started its 3 demos for today."],
    ["demo_budget", "Today's demo spots are taken", "Every demo spot for today is used."],
  ])("explains a %s refusal with the server's message and ways forward that never dead-end", async (code, title, message) => {
    server.use(http.post("*/api/v1/demo/start", () => HttpResponse.json({ code, message }, { status: 429 })));
    mount();
    expect(await screen.findByRole("heading", { name: title })).toBeInTheDocument();
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign up free" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: "Browse the matchday" })).toHaveAttribute("href", "/matchday");
    expect(screen.getByRole("link", { name: "See the track record" })).toHaveAttribute("href", "/track-record");
    expect(screen.getByRole("link", { name: "Watch the recorded replay" })).toHaveAttribute("href", "/#demo");
    expect(navigate).not.toHaveBeenCalled();
  });

  it("falls back to its own wording when a 429 carries no message", async () => {
    server.use(http.post("*/api/v1/demo/start", () => HttpResponse.json({}, { status: 429 })));
    mount();
    expect(await screen.findByRole("heading", { name: "Too many demos from this network today" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign up free" })).toBeInTheDocument();
  });

  it("lets the visitor retry after any other failure", async () => {
    server.use(http.post("*/api/v1/demo/start", () => HttpResponse.json({ code: "unavailable", message: "x" }, { status: 503 })));
    mount();
    expect(await screen.findByText(/couldn't start the demo/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign up free" })).toBeInTheDocument();
  });

  it("treats a dropped connection as a failure that can be retried", async () => {
    server.use(http.post("*/api/v1/demo/start", () => HttpResponse.error()));
    mount();
    expect(await screen.findByText(/couldn't start the demo/i)).toBeInTheDocument();
    const starts = countStarts();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/matchday"));
    expect(starts.count).toBe(1);
  });
});

describe("DemoStarter when already signed in", () => {
  it("sends a demo user straight back to the matchday without starting another", async () => {
    setMockSession("demo");
    const starts = countStarts();
    mount();
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/matchday"));
    expect(starts.count).toBe(0);
  });

  it("tells a regular user a demo is a separate account and lets them go back or sign out first", async () => {
    setMockSession("free");
    const starts = countStarts();
    mount();
    expect(await screen.findByRole("heading", { name: "You're already signed in" })).toBeInTheDocument();
    expect(screen.getByText(/sam\.rivera@example\.com/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to the matchday" })).toHaveAttribute("href", "/matchday");
    expect(starts.count).toBe(0);

    await userEvent.click(screen.getByRole("button", { name: "Sign out and start a demo" }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/matchday"));
    expect(starts.count).toBe(1);
  });
});
