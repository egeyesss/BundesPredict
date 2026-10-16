import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiMockingGate } from "./ApiMockingGate";

const enableApiMocking = vi.fn<() => Promise<void>>();
vi.mock("@/lib/api/mocks/browser", () => ({ enableApiMocking: () => enableApiMocking() }));

afterEach(() => {
  vi.unstubAllEnvs();
  enableApiMocking.mockReset();
});

describe("ApiMockingGate", () => {
  it("renders its children straight away when mocking is off", () => {
    render(
      <ApiMockingGate>
        <p>page</p>
      </ApiMockingGate>,
    );
    expect(screen.getByText("page")).toBeInTheDocument();
    expect(enableApiMocking).not.toHaveBeenCalled();
  });

  it("holds the children back until the mock worker is running", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MOCKING", "enabled");
    let release: () => void = () => {};
    enableApiMocking.mockReturnValue(new Promise<void>((resolve) => (release = resolve)));

    render(
      <ApiMockingGate>
        <p>page</p>
      </ApiMockingGate>,
    );
    expect(screen.queryByText("page")).not.toBeInTheDocument();

    release();
    await waitFor(() => expect(screen.getByText("page")).toBeInTheDocument());
  });
});
