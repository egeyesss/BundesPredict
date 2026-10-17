import { describe, expect, it } from "vitest";

import { isCurrentSection, islandMode, sectionLabel } from "./island";

const idle = { hover: false, focus: false, menuOpen: false };

describe("islandMode", () => {
  it("is full at the top of a wide page", () => {
    expect(islandMode({ ...idle, width: 1440, scrollY: 0 })).toBe("full");
  });

  it("is still full just under the 60px scroll threshold", () => {
    expect(islandMode({ ...idle, width: 1440, scrollY: 59 })).toBe("full");
  });

  it("compacts once scrolled past 60px", () => {
    expect(islandMode({ ...idle, width: 1440, scrollY: 60 })).toBe("compact");
  });

  it("expands a compact island on hover or keyboard focus", () => {
    expect(islandMode({ ...idle, width: 1440, scrollY: 800, hover: true })).toBe("full");
    expect(islandMode({ ...idle, width: 1440, scrollY: 800, focus: true })).toBe("full");
  });

  it("switches to the mobile layout under 800px", () => {
    expect(islandMode({ ...idle, width: 799, scrollY: 0 })).toBe("mobile");
    expect(islandMode({ ...idle, width: 800, scrollY: 0 })).toBe("full");
  });

  it("ignores scroll and hover on mobile", () => {
    expect(islandMode({ ...idle, width: 375, scrollY: 900, hover: true })).toBe("mobile");
  });

  it("opens the menu panel on mobile only", () => {
    expect(islandMode({ ...idle, width: 375, scrollY: 0, menuOpen: true })).toBe("open");
    expect(islandMode({ ...idle, width: 1440, scrollY: 0, menuOpen: true })).toBe("full");
  });
});

describe("sectionLabel", () => {
  it.each([
    ["/", "Chat"],
    ["/matchday", "Matchday"],
    ["/matchday/7", "Matchday"],
    ["/chat/abc", "Chat"],
    ["/track-record", "Track record"],
    ["/account", "Account"],
    ["/login", "Sign in"],
    ["/styleguide", "Styleguide"],
    ["/somewhere-else", "BundesPredict"],
  ])("%s reads as %s", (pathname, label) => {
    expect(sectionLabel(pathname)).toBe(label);
  });
});

describe("isCurrentSection", () => {
  it("treats the chat demo at / as the Chat section", () => {
    expect(isCurrentSection("/", "/chat")).toBe(true);
  });

  it("matches nested routes but not sibling prefixes", () => {
    expect(isCurrentSection("/matchday/7", "/matchday")).toBe(true);
    expect(isCurrentSection("/matchdays", "/matchday")).toBe(false);
  });

  it("is false for other sections", () => {
    expect(isCurrentSection("/matchday", "/chat")).toBe(false);
  });
});
