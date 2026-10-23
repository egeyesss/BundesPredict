import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw/http";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "@/lib/api/mocks/node";
import { setupApiMocks } from "@/lib/api/mocks/vitest";

const navigate = vi.hoisted(() => vi.fn());
vi.mock("@/lib/navigate", () => ({ navigate }));

import { DemoStarter } from "./DemoStarter";

setupApiMocks();

beforeEach(() => navigate.mockReset());

describe("DemoStarter", () => {
  it("creates the demo account once and opens the matchday", async () => {
    let starts = 0;
    server.use(
      http.post("*/api/v1/demo/start", () => {
        starts += 1;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    render(<DemoStarter />);
    expect(screen.getByRole("status")).toHaveTextContent(/setting up your demo/i);
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/matchday"));
    expect(starts).toBe(1);
  });

  it("explains the daily limit and offers the email sign-in instead", async () => {
    server.use(http.post("*/api/v1/demo/start", () => HttpResponse.json({ code: "rate_limited", message: "x" }, { status: 429 })));
    render(<DemoStarter />);
    expect(await screen.findByText(/too many demos/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in with email" })).toHaveAttribute("href", "/login");
    expect(navigate).not.toHaveBeenCalled();
  });

  it("lets the visitor retry after any other failure", async () => {
    server.use(http.post("*/api/v1/demo/start", () => HttpResponse.json({ code: "unavailable", message: "x" }, { status: 503 })));
    render(<DemoStarter />);
    expect(await screen.findByText(/couldn't start the demo/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
