import { describe, expect, it } from "vitest";

import { DEFAULT_NEXT_PATH, loginUrl, safeNextPath } from "./next-path";

describe("safeNextPath", () => {
  it("keeps a same-site path with its query and hash", () => {
    expect(safeNextPath("/account?checkout=success")).toBe("/account?checkout=success");
    expect(safeNextPath("/chat/abc#top")).toBe("/chat/abc#top");
  });

  it.each([
    ["an absolute URL", "https://evil.example/phish"],
    ["a protocol-relative URL", "//evil.example"],
    ["a backslash trick", "/\\evil.example"],
    ["a scheme", "javascript:alert(1)"],
    ["a path without a leading slash", "account"],
    ["an empty string", ""],
    ["the login page itself", "/login?next=/account"],
    ["a control character", "/account\n/evil"],
  ])("falls back for %s", (_label, raw) => {
    expect(safeNextPath(raw)).toBe(DEFAULT_NEXT_PATH);
  });

  it("falls back for missing or repeated params", () => {
    expect(safeNextPath(undefined)).toBe(DEFAULT_NEXT_PATH);
    expect(safeNextPath(["/a", "/b"])).toBe(DEFAULT_NEXT_PATH);
  });
});

describe("loginUrl", () => {
  it("encodes the path the visitor wanted", () => {
    expect(loginUrl("/chat?fixture=803")).toBe("/login?next=%2Fchat%3Ffixture%3D803");
  });

  it("omits next when it would just be the default", () => {
    expect(loginUrl(DEFAULT_NEXT_PATH)).toBe("/login");
  });
});
