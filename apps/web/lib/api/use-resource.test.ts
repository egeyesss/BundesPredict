import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiFailure, useResource } from "./use-resource";

describe("useResource", () => {
  it("goes from loading to ready with the loaded data", async () => {
    const { result } = renderHook(() => useResource(async () => "odds", "key"));
    expect(result.current.resource).toEqual({ status: "loading" });
    await waitFor(() => expect(result.current.resource).toEqual({ status: "ready", data: "odds" }));
  });

  it("reports the failure the loader threw", async () => {
    const failure = new ApiFailure(401, "not_authenticated", "Sign in to continue.");
    const { result } = renderHook(() =>
      useResource(async () => {
        throw failure;
      }, "key"),
    );
    await waitFor(() => expect(result.current.resource).toEqual({ status: "error", failure }));
  });

  it("wraps an unexpected throw as a status 0 failure", async () => {
    const { result } = renderHook(() =>
      useResource(async () => {
        throw new TypeError("Failed to fetch");
      }, "key"),
    );
    await waitFor(() => expect(result.current.resource.status).toBe("error"));
    expect(result.current.resource).toMatchObject({ failure: { status: 0, code: "network_error" } });
  });

  it("loads again when the key changes and when reload is called", async () => {
    const load = vi.fn(async () => "x");
    const { result, rerender } = renderHook(({ key }) => useResource(load, key), { initialProps: { key: "a" } });
    await waitFor(() => expect(result.current.resource.status).toBe("ready"));
    rerender({ key: "b" });
    await waitFor(() => expect(load).toHaveBeenCalledTimes(2));
    act(() => result.current.reload());
    await waitFor(() => expect(load).toHaveBeenCalledTimes(3));
  });

  it("does nothing while the key is null", () => {
    const load = vi.fn(async () => "x");
    const { result } = renderHook(() => useResource(load, null));
    expect(result.current.resource).toEqual({ status: "idle" });
    expect(load).not.toHaveBeenCalled();
  });

  it("ignores an answer that arrives after the key moved on", async () => {
    let finishFirst: (value: string) => void = () => {};
    const load = vi.fn((signal: AbortSignal) => {
      void signal;
      return load.mock.calls.length === 1 ? new Promise<string>((resolve) => (finishFirst = resolve)) : Promise.resolve("second");
    });
    const { result, rerender } = renderHook(({ key }) => useResource(load, key), { initialProps: { key: "a" } });
    rerender({ key: "b" });
    await waitFor(() => expect(result.current.resource).toEqual({ status: "ready", data: "second" }));
    await act(async () => finishFirst("first"));
    expect(result.current.resource).toEqual({ status: "ready", data: "second" });
  });
});
