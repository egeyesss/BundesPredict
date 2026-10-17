import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw/http";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { meFor } from "@/lib/api/mocks/data";
import { server } from "@/lib/api/mocks/node";
import { setMockSession } from "@/lib/api/mocks/session";
import { setupApiMocks } from "@/lib/api/mocks/vitest";

const navigate = vi.hoisted(() => vi.fn());
vi.mock("@/lib/navigate", () => ({ navigate }));
vi.mock("@/components/signature/AgentOrb", () => ({ AgentOrb: ({ state }: { state: { phase: string } }) => <span data-testid="orb">{state.phase}</span> }));

import { CheckoutReturn } from "./CheckoutReturn";
import { SessionProvider } from "./SessionProvider";

setupApiMocks();

const mount = (props: Partial<React.ComponentProps<typeof CheckoutReturn>> = {}) =>
  render(
    <SessionProvider>
      <CheckoutReturn initialMe={meFor("free")} pollMs={20} slowAfterMs={150} {...props} />
    </SessionProvider>,
  );

beforeEach(() => {
  navigate.mockReset();
  setMockSession("free");
});

describe("CheckoutReturn", () => {
  it("waits on the webhook and never claims Pro while /me still says free", async () => {
    let polls = 0;
    server.use(
      http.get("*/api/v1/me", () => {
        polls += 1;
        return HttpResponse.json(meFor("free"));
      }),
    );
    mount();
    expect(screen.getByRole("heading", { name: "Confirming your payment" })).toBeInTheDocument();
    await waitFor(() => expect(polls).toBeGreaterThan(3));
    expect(screen.queryByText("You're on Pro")).not.toBeInTheDocument();
    expect(screen.getByTestId("orb")).toHaveTextContent("thinking");
  });

  it("flips to Pro as soon as /me reports it", async () => {
    let polls = 0;
    server.use(
      http.get("*/api/v1/me", () => {
        polls += 1;
        return HttpResponse.json(polls > 3 ? meFor("pro") : meFor("free"));
      }),
    );
    mount();
    expect(await screen.findByRole("heading", { name: "You're on Pro" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to chat" })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("link", { name: "Account" })).toHaveAttribute("href", "/account");
    expect(screen.getByTestId("orb")).toHaveTextContent(/done|idle/);
  });

  it("shows Pro straight away for an account that already is Pro", () => {
    mount({ initialMe: meFor("pro") });
    expect(screen.getByRole("heading", { name: "You're on Pro" })).toBeInTheDocument();
  });

  it("says Stripe is slow after the threshold but keeps checking", async () => {
    let polls = 0;
    server.use(
      http.get("*/api/v1/me", () => {
        polls += 1;
        return HttpResponse.json(polls > 25 ? meFor("pro") : meFor("free"));
      }),
    );
    mount();
    expect(await screen.findByRole("heading", { name: "Still waiting on Stripe" })).toBeInTheDocument();
    expect(screen.queryByText("You're on Pro")).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "You're on Pro" })).toBeInTheDocument();
  });

  it("sends a session that expired mid-poll back to login", async () => {
    server.use(http.get("*/api/v1/me", () => HttpResponse.json({ code: "not_authenticated", message: "x" }, { status: 401 })));
    mount();
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/login?next=%2Faccount%3Fcheckout%3Dsuccess"));
  });

  it("keeps polling through a network error", async () => {
    let polls = 0;
    server.use(
      http.get("*/api/v1/me", () => {
        polls += 1;
        return polls < 3 ? HttpResponse.error() : HttpResponse.json(meFor("pro"));
      }),
    );
    mount();
    expect(await screen.findByRole("heading", { name: "You're on Pro" })).toBeInTheDocument();
  });
});
