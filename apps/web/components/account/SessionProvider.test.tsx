import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw/http";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "@/lib/api/mocks/node";
import { setMockSession } from "@/lib/api/mocks/session";
import { setupApiMocks } from "@/lib/api/mocks/vitest";

vi.mock("@/lib/account/timezone", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/account/timezone")>()),
  browserTimeZone: () => "Europe/Berlin",
}));

import { SessionProvider, useSession } from "./SessionProvider";

setupApiMocks();

function Probe() {
  const { state } = useSession();
  return <p data-testid="state">{state.status === "ready" ? `ready:${state.me.email}` : state.status}</p>;
}

const mount = () =>
  render(
    <SessionProvider>
      <Probe />
    </SessionProvider>,
  );

describe("SessionProvider", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("starts loading, then exposes the signed-in account", async () => {
    setMockSession("free");
    mount();
    expect(screen.getByTestId("state")).toHaveTextContent("loading");
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("ready:sam.rivera@example.com"));
  });

  it("reports signed_out on a 401", async () => {
    mount();
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("signed_out"));
  });

  it("reports error, not signed_out, when the API fails", async () => {
    server.use(http.get("*/api/v1/me", () => HttpResponse.json({}, { status: 500 })));
    mount();
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("error"));
  });

  it("silently reports the browser time zone with no source when it differs from the saved one", async () => {
    setMockSession("free");
    const bodies: unknown[] = [];
    server.use(
      http.patch("*/api/v1/me", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ ...(await fetchFreeMe()), timezone: "Europe/Berlin" });
      }),
    );
    mount();
    await waitFor(() => expect(bodies).toEqual([{ timezone: "Europe/Berlin" }]));
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("ready"));
  });

  it("does not report when the saved zone already matches", async () => {
    setMockSession("free");
    const bodies: unknown[] = [];
    server.use(
      http.get("*/api/v1/me", async () => HttpResponse.json({ ...(await fetchFreeMe()), timezone: "Europe/Berlin" })),
      http.patch("*/api/v1/me", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(await fetchFreeMe());
      }),
    );
    mount();
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("ready"));
    expect(bodies).toEqual([]);
  });
});

async function fetchFreeMe() {
  const { meFor } = await import("@/lib/api/mocks/data");
  return meFor("free");
}
