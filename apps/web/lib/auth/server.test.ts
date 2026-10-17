import { http, HttpResponse } from "msw/http";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "@/lib/api/mocks/node";
import { setupApiMocks } from "@/lib/api/mocks/vitest";

const cookieHeader = vi.hoisted(() => ({ value: "" }));
vi.mock("next/headers", () => ({ cookies: async () => ({ toString: () => cookieHeader.value }) }));
vi.mock("next/navigation", () => ({
  redirect: (url: string) => {
    throw new Error(`NEXT_REDIRECT:${url}`);
  },
}));

import { getMe, requireMe } from "./server";

setupApiMocks();

beforeEach(() => {
  cookieHeader.value = "";
  vi.stubEnv("API_BASE_URL", "http://api.mock.test");
  vi.stubEnv("PROXY_SECRET", "s3cret");
});

describe("getMe", () => {
  it("forwards the visitor's cookie and the proxy secret to Django", async () => {
    let seen: Headers | null = null;
    server.use(
      http.get("*/api/v1/me", ({ request }) => {
        seen = request.headers;
        return HttpResponse.json({ id: 1 });
      }),
    );
    cookieHeader.value = "sessionid=abc; csrftoken=def";
    await getMe();
    expect(seen!.get("cookie")).toBe("sessionid=abc; csrftoken=def");
    expect(seen!.get("x-proxy-secret")).toBe("s3cret");
  });

  it("returns the account when signed in", async () => {
    cookieHeader.value = "bp_mock_plan=free";
    const outcome = await getMe();
    expect(outcome).toMatchObject({ status: "ok", me: { plan: "free" } });
  });

  it("says signed_out on a 401", async () => {
    expect(await getMe()).toEqual({ status: "signed_out" });
  });

  it("says error on a server failure or a dropped connection, never signed_out", async () => {
    server.use(http.get("*/api/v1/me", () => HttpResponse.json({}, { status: 502 })));
    expect(await getMe()).toEqual({ status: "error" });
    server.use(http.get("*/api/v1/me", () => HttpResponse.error()));
    expect(await getMe()).toEqual({ status: "error" });
  });
});

describe("requireMe", () => {
  it("returns the account when signed in", async () => {
    cookieHeader.value = "bp_mock_plan=pro";
    expect((await requireMe("/account")).plan).toBe("pro");
  });

  it("redirects a signed-out visitor to login with the path they wanted", async () => {
    await expect(requireMe("/chat?fixture=803")).rejects.toThrow("NEXT_REDIRECT:/login?next=%2Fchat%3Ffixture%3D803");
  });

  it("throws instead of redirecting when the API is down", async () => {
    server.use(http.get("*/api/v1/me", () => HttpResponse.json({}, { status: 500 })));
    await expect(requireMe("/account")).rejects.toThrow(/account/i);
  });
});
