import { describe, expect, it } from "vitest";

import robots from "./robots";
import sitemap from "./sitemap";

const entries = sitemap();

describe("sitemap", () => {
  it("lists the public pages on the production origin", () => {
    const urls = entries.map((entry) => entry.url);
    for (const path of ["/", "/matchday", "/track-record", "/how-its-built", "/legal/terms", "/legal/privacy", "/legal/refunds"]) {
      expect(urls).toContain(`https://bundespredict.egeyesilyurt.ca${path === "/" ? "" : path}`);
    }
  });

  it("leaves out pages that need a session", () => {
    const urls = entries.map((entry) => entry.url).join(" ");
    expect(urls).not.toMatch(/\/(account|chat|login|admin|demo)/);
  });
});

describe("robots", () => {
  it("allows crawling, hides the private routes and points at the sitemap", () => {
    const result = robots();
    expect(result.sitemap).toBe("https://bundespredict.egeyesilyurt.ca/sitemap.xml");
    expect(result.rules).toMatchObject({ userAgent: "*", allow: "/" });
    const disallow = (result.rules as { disallow: string[] }).disallow;
    expect(disallow).toEqual(expect.arrayContaining(["/api/", "/account", "/chat", "/admin", "/demo"]));
  });
});
