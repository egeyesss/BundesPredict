import { afterEach, describe, expect, it } from "vitest";

import { findAnchor, isVisible } from "./anchors";

function mount(html: string) {
  document.body.innerHTML = html;
  for (const element of document.body.querySelectorAll<HTMLElement>("[data-laid-out]")) {
    element.getClientRects = () => [new DOMRect(0, 0, 10, 10)] as unknown as DOMRectList;
  }
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("findAnchor", () => {
  it("picks the first laid-out element for a name", () => {
    mount(`<i data-tour="fixture" id="hidden"></i><i data-tour="fixture" data-laid-out id="first"></i><i data-tour="fixture" data-laid-out id="second"></i>`);
    expect(findAnchor(["fixture"])?.id).toBe("first");
  });

  it("falls back to the next name when the first is missing", () => {
    mount(`<i data-tour="composer" data-laid-out id="composer"></i>`);
    expect(findAnchor(["message", "composer"])?.id).toBe("composer");
    expect(findAnchor(["message"])).toBeNull();
  });

  it("skips elements inside an inert layer", () => {
    mount(`<div inert><i data-tour="upgrade" data-laid-out id="off"></i></div><div><i data-tour="upgrade" data-laid-out id="on"></i></div>`);
    expect(findAnchor(["upgrade"])?.id).toBe("on");
    expect(isVisible(document.getElementById("off")!)).toBe(false);
  });
});
