import { describe, expect, it } from "vitest";

import { browserTimeZone, timeZoneOptions } from "./timezone";

describe("timeZoneOptions", () => {
  it("lists IANA zones and always includes the ones asked for", () => {
    const options = timeZoneOptions(["Mars/Olympus_Mons", null]);
    expect(options).toContain("America/Toronto");
    expect(options).toContain("Europe/Berlin");
    expect(options).toContain("Mars/Olympus_Mons");
    expect(options.filter((zone) => zone === "Mars/Olympus_Mons")).toHaveLength(1);
  });

  it("is sorted", () => {
    const options = timeZoneOptions([]);
    expect(options).toEqual([...options].sort());
  });
});

describe("browserTimeZone", () => {
  it("returns an IANA name", () => {
    expect(browserTimeZone()).toMatch(/^[A-Za-z_]+(\/[A-Za-z_+\-0-9]+)*$/);
  });
});
