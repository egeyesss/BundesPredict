import { describe, expect, it } from "vitest";

import { MOCK_PLAN_COOKIE, SESSION_COOKIE, signedInHomePath } from "./session-cookie";

const jar = (...names: string[]) => ({ has: (name: string) => names.includes(name) });

describe("signedInHomePath", () => {
  it("sends a visitor with a session cookie from the landing page to the matchday", () => {
    expect(signedInHomePath("/", jar(SESSION_COOKIE))).toBe("/matchday");
  });

  it("leaves anonymous visitors on the landing page", () => {
    expect(signedInHomePath("/", jar())).toBeNull();
  });

  it("only acts on the landing page", () => {
    expect(signedInHomePath("/how-its-built", jar(SESSION_COOKIE))).toBeNull();
    expect(signedInHomePath("/legal/terms", jar(SESSION_COOKIE))).toBeNull();
  });

  it("counts the mock plan cookie only while mocking is on", () => {
    expect(signedInHomePath("/", jar(MOCK_PLAN_COOKIE))).toBeNull();
    process.env.API_MOCKING = "enabled";
    try {
      expect(signedInHomePath("/", jar(MOCK_PLAN_COOKIE))).toBe("/matchday");
    } finally {
      delete process.env.API_MOCKING;
    }
  });
});
