import { describe, expect, it } from "vitest";

import { volumeNames } from "./volume-names.mjs";

describe("volumeNames", () => {
  it("gives two checkouts of the repo separate volumes", () => {
    const main = volumeNames("/Users/dev/BundesPredict", "arm64");
    const worktree = volumeNames("/Users/dev/BundesPredict-worktrees/track-record", "arm64");

    expect(main.nodeModules).not.toBe(worktree.nodeModules);
    expect(main.nextCache).not.toBe(worktree.nextCache);
  });

  it("reuses the same volumes for the same checkout and arch", () => {
    expect(volumeNames("/Users/dev/BundesPredict", "arm64")).toEqual(
      volumeNames("/Users/dev/BundesPredict", "arm64"),
    );
  });

  it("keeps native binaries of different arches apart", () => {
    const arm = volumeNames("/Users/dev/BundesPredict", "arm64");
    const x64 = volumeNames("/Users/dev/BundesPredict", "x64");

    expect(arm.nodeModules).not.toBe(x64.nodeModules);
  });

  it("only uses characters docker accepts in a volume name", () => {
    const { nodeModules, nextCache } = volumeNames("/Users/dev/Bundes Predict (copy)", "arm64");

    expect(nodeModules).toMatch(/^[a-zA-Z0-9][a-zA-Z0-9_.-]+$/);
    expect(nextCache).toMatch(/^[a-zA-Z0-9][a-zA-Z0-9_.-]+$/);
  });
});
