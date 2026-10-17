import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw/http";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "@/lib/api/mocks/node";
import { setMockSession } from "@/lib/api/mocks/session";
import { setupApiMocks } from "@/lib/api/mocks/vitest";

const navigate = vi.hoisted(() => vi.fn());
vi.mock("@/lib/navigate", () => ({ navigate }));

import { useBillingRedirect } from "./useBillingRedirect";
import { useSignOut } from "./useSignOut";

setupApiMocks();

beforeEach(() => {
  navigate.mockReset();
  setMockSession("free");
});

describe("useBillingRedirect", () => {
  it("sends the browser to the Stripe Checkout URL", async () => {
    const { result } = renderHook(() => useBillingRedirect());
    await act(() => result.current.start("checkout"));
    expect(navigate).toHaveBeenCalledWith("https://checkout.stripe.com/c/pay/cs_test_mock");
    expect(result.current.pending).toBe("checkout");
  });

  it("opens the portal", async () => {
    const { result } = renderHook(() => useBillingRedirect());
    await act(() => result.current.start("portal"));
    expect(navigate).toHaveBeenCalledWith("https://billing.stripe.com/p/session/test_mock");
  });

  it("explains a missing billing account and re-enables the button", async () => {
    server.use(
      http.post("*/api/v1/billing/portal", () =>
        HttpResponse.json({ code: "no_billing_account", message: "This account has no billing history yet." }, { status: 404 }),
      ),
    );
    const { result } = renderHook(() => useBillingRedirect());
    await act(() => result.current.start("portal"));
    expect(navigate).not.toHaveBeenCalled();
    expect(result.current.pending).toBeNull();
    expect(result.current.error).toMatch(/no billing history/i);
  });

  it("sends a signed-out visitor to login", async () => {
    server.use(http.post("*/api/v1/billing/checkout", () => HttpResponse.json({ code: "not_authenticated", message: "x" }, { status: 401 })));
    const { result } = renderHook(() => useBillingRedirect());
    await act(() => result.current.start("checkout"));
    expect(navigate).toHaveBeenCalledWith("/login?next=%2Faccount");
  });

  it("reports other failures through onError", async () => {
    server.use(http.post("*/api/v1/billing/checkout", () => HttpResponse.json({}, { status: 502 })));
    const onError = vi.fn();
    const { result } = renderHook(() => useBillingRedirect({ onError }));
    await act(() => result.current.start("checkout"));
    expect(onError).toHaveBeenCalledWith(expect.stringMatching(/couldn't reach stripe/i));
    await waitFor(() => expect(result.current.pending).toBeNull());
  });
});

describe("useSignOut", () => {
  it("logs out and goes to the login page", async () => {
    const { result } = renderHook(() => useSignOut());
    await act(() => result.current.signOut());
    expect(navigate).toHaveBeenCalledWith("/login");
  });

  it("stays put and reports when logout fails", async () => {
    server.use(http.delete("*/_allauth/browser/v1/auth/session", () => HttpResponse.json({}, { status: 500 })));
    const onError = vi.fn();
    const { result } = renderHook(() => useSignOut({ onError }));
    await act(() => result.current.signOut());
    expect(navigate).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith(expect.stringMatching(/sign you out/i));
  });
});
