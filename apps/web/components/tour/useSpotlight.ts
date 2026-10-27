"use client";

import { useEffect, useState, type RefObject } from "react";

import { findAnchor } from "./anchors";
import { overlapsSheet, placeBubble, sheetDockFor, SHEET_BREAKPOINT, type Box, type Dock } from "./placement";
import type { TourStep } from "./steps";

export type AnchorStatus = "searching" | "found" | "missing";

const SPOT_PADDING = 8;
const NAV_HEIGHT = 76;
const MISSING_AFTER_MS = 10_000;
const SETTLE_MS = 700;
const REALIGN_WINDOW_MS = 4000;
const REALIGN_EVERY_MS = 400;
const PREPARE_EVERY_MS = 200;
const TRACKING_HOLD_MS = 160;
const SHEET_EDGE = 12;

export type SpotlightRefs = {
  layer: RefObject<HTMLDivElement | null>;
  spot: RefObject<HTMLDivElement | null>;
  bubble: RefObject<HTMLDivElement | null>;
  arrow: RefObject<HTMLSpanElement | null>;
};

/** Height of everything fixed at the top of the page: the demo bar and the island. */
function headerHeight(): number {
  const bar = Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--demo-bar-h"));
  return NAV_HEIGHT + (Number.isFinite(bar) ? bar : 0);
}

function boxOf(rect: DOMRect): Box {
  return { left: rect.left, top: rect.top, width: rect.width, height: rect.height, right: rect.right, bottom: rect.bottom };
}

/** Opens the track record tab a stop lives on; the page keeps both panels but mounts only the selected one's charts. */
function prepareStep(step: TourStep) {
  if (!step.tab) return;
  const tab = document.getElementById(`tab-${step.tab}`);
  if (tab && tab.getAttribute("aria-selected") === "false") tab.click();
}

type AlignInput = { sheet: boolean; dock: Dock; bubbleHeight: number; reduced: boolean };

const SLACK = 20;
const MIN_FREE_HEIGHT = 40;

/** Every ancestor that scrolls on its own, innermost first, ending with the page itself. */
function scrollParents(element: HTMLElement): (HTMLElement | null)[] {
  const parents: (HTMLElement | null)[] = [];
  for (let parent = element.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
    const { overflowY } = getComputedStyle(parent);
    if (overflowY === "auto" || overflowY === "scroll") parents.push(parent);
  }
  return [...parents, null];
}

/** Anchors inside an inner scroller (the chat log) can always be scrolled clear of a bottom sheet; others dock away from where they are. */
function dockFor(element: HTMLElement, rect: Box, viewportHeight: number): Dock {
  return scrollParents(element).length > 1 ? "bottom" : sheetDockFor(rect, viewportHeight);
}

/**
 * Scrolls the anchor into the part of the screen the bubble leaves free, and leaves it alone when
 * it is already there. Each scrolling ancestor is moved by only as much as it needs, because
 * `scrollIntoView` on a nested scroller can park the anchor behind the chat composer or the sheet.
 */
function align(element: HTMLElement, { sheet, dock, bubbleHeight, reduced }: AlignInput) {
  const header = headerHeight();
  const viewportHeight = window.innerHeight;
  const freeTop = sheet && dock === "top" ? header + bubbleHeight + 20 : header + 16;
  const freeBottom = sheet && dock === "bottom" ? viewportHeight - bubbleHeight - 28 : viewportHeight - 16;
  const behavior = reduced ? "auto" : "smooth";

  const rect = element.getBoundingClientRect();
  let top = rect.top;
  for (const scroller of scrollParents(element)) {
    const box = scroller ? scroller.getBoundingClientRect() : { top: 0, bottom: viewportHeight };
    const visibleTop = Math.max(box.top, freeTop);
    const visibleBottom = Math.min(box.bottom, freeBottom);
    const room = visibleBottom - visibleTop;
    if (room < MIN_FREE_HEIGHT) continue;
    // The page itself is only moved when the anchor is out of sight; an inner scroller is always centred, so the stop looks the same however long the content took to load.
    if (scroller === null && top >= visibleTop - SLACK && top + rect.height <= visibleBottom + SLACK) continue;

    const wanted = rect.height >= room ? visibleTop : visibleTop + (room - rect.height) / 2;
    const current = scroller ? scroller.scrollTop : window.scrollY;
    const limit = scroller ? scroller.scrollHeight - scroller.clientHeight : document.documentElement.scrollHeight - viewportHeight;
    const delta = Math.min(Math.max(top - wanted, -current), Math.max(limit - current, 0));
    if (Math.abs(delta) < 1) continue;
    if (scroller) scroller.scrollBy({ top: delta, behavior });
    else window.scrollBy({ top: delta, behavior });
    top -= delta;
  }
}

/**
 * Keeps the spotlight and the bubble glued to a step's anchor. One animation-frame loop reads the
 * anchor's rectangle and writes styles straight to the DOM, so following a scroll costs no React
 * renders and has no lag. The spring only plays when the anchor moves without a scroll.
 */
export function useSpotlight(step: TourStep, active: boolean, refs: SpotlightRefs, reduced: boolean): AnchorStatus {
  const [found, setFound] = useState<{ stepId: string; status: AnchorStatus }>({ stepId: step.id, status: "searching" });
  const { layer, spot, bubble, arrow } = refs;

  useEffect(() => {
    if (!active) return;

    const stepId = step.id;
    const setStatus = (status: AnchorStatus) =>
      setFound((previous) => (previous.stepId === stepId && previous.status === status ? previous : { stepId, status }));
    const startedAt = performance.now();
    let current: HTMLElement | null = null;
    let alignedAt = 0;
    let lastRealign = 0;
    let settled = true;
    let dock: Dock | null = null;
    let lastPrepare = 0;
    let lastKey = "";
    let raf = 0;
    let trackingTimer: ReturnType<typeof setTimeout> | undefined;

    const markTracking = () => {
      layer.current?.classList.add("tracking");
      clearTimeout(trackingTimer);
      trackingTimer = setTimeout(() => layer.current?.classList.remove("tracking"), TRACKING_HOLD_MS);
    };
    window.addEventListener("scroll", markTracking, { passive: true, capture: true });
    window.addEventListener("resize", markTracking);

    const apply = (element: HTMLElement) => {
      const spotEl = spot.current;
      const bubbleEl = bubble.current;
      if (!spotEl || !bubbleEl) return;
      const rect = boxOf(element.getBoundingClientRect());
      const viewport = { width: window.innerWidth, height: window.innerHeight };
      const size = { width: bubbleEl.offsetWidth, height: bubbleEl.offsetHeight };
      const sheet = viewport.width < SHEET_BREAKPOINT;
      dock ??= sheet ? dockFor(element, rect, viewport.height) : "bottom";

      if (!settled && performance.now() - alignedAt > SETTLE_MS) {
        settled = true;
        if (sheet && scrollParents(element).length === 1 && overlapsSheet(rect, dock, size.height, viewport.height, headerHeight())) {
          dock = dock === "bottom" ? "top" : "bottom";
          alignedAt = performance.now();
          settled = false;
          align(element, { sheet, dock, bubbleHeight: size.height, reduced });
          return;
        }
      }

      const placement = placeBubble({ target: rect, bubble: size, viewport, preferred: step.side, headerHeight: headerHeight() });
      const key = [rect.left, rect.top, rect.width, rect.height, size.width, size.height, placement.side, placement.x, placement.y, dock].join("|");
      if (key === lastKey) return;
      lastKey = key;

      Object.assign(spotEl.style, {
        display: "block",
        left: `${rect.left - SPOT_PADDING}px`,
        top: `${rect.top - SPOT_PADDING}px`,
        width: `${rect.width + SPOT_PADDING * 2}px`,
        height: `${rect.height + SPOT_PADDING * 2}px`,
      });
      bubbleEl.dataset.side = placement.side;
      if (placement.side === "sheet") {
        Object.assign(bubbleEl.style, {
          left: `${placement.x}px`,
          top: dock === "top" ? `${headerHeight() + SHEET_EDGE}px` : "auto",
          bottom: dock === "top" ? "auto" : `calc(${SHEET_EDGE}px + env(safe-area-inset-bottom, 0px))`,
        });
      } else {
        Object.assign(bubbleEl.style, { left: `${placement.x}px`, top: `${placement.y}px`, bottom: "auto" });
        const arrowEl = arrow.current;
        if (arrowEl && placement.arrow !== null) {
          if (placement.side === "top" || placement.side === "bottom") Object.assign(arrowEl.style, { left: `${placement.arrow}px`, top: "" });
          else Object.assign(arrowEl.style, { top: `${placement.arrow}px`, left: "" });
        }
      }
    };

    const frame = (now: number) => {
      if (now - lastPrepare > PREPARE_EVERY_MS) {
        lastPrepare = now;
        prepareStep(step);
      }

      if (!current || !current.isConnected || current.getClientRects().length === 0) {
        const found = findAnchor(step.anchors);
        if (found !== current) {
          current = found;
          settled = false;
          dock = null;
          lastKey = "";
          if (found) {
            const sheet = window.innerWidth < SHEET_BREAKPOINT;
            const size = bubble.current?.offsetHeight ?? 0;
            dock = sheet ? dockFor(found, boxOf(found.getBoundingClientRect()), window.innerHeight) : "bottom";
            alignedAt = now;
            align(found, { sheet, dock, bubbleHeight: size, reduced });
            if (spot.current) spot.current.dataset.fresh = "";
            requestAnimationFrame(() => requestAnimationFrame(() => spot.current && delete spot.current.dataset.fresh));
          }
        }
      }

      if (current) {
        setStatus("found");
        // Charts and lists keep loading for a moment after the anchor appears, which can push it off screen again.
        if (now - alignedAt < REALIGN_WINDOW_MS && now - lastRealign > REALIGN_EVERY_MS) {
          lastRealign = now;
          const sheet = window.innerWidth < SHEET_BREAKPOINT;
          align(current, { sheet, dock: dock ?? "bottom", bubbleHeight: bubble.current?.offsetHeight ?? 0, reduced });
        }
        apply(current);
      } else {
        if (spot.current) spot.current.style.display = "none";
        const bubbleEl = bubble.current;
        if (bubbleEl) {
          bubbleEl.dataset.side = "center";
          Object.assign(bubbleEl.style, { left: "", top: "", bottom: "" });
        }
        lastKey = "";
        setStatus(now - startedAt > MISSING_AFTER_MS ? "missing" : "searching");
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(trackingTimer);
      window.removeEventListener("scroll", markTracking, { capture: true });
      window.removeEventListener("resize", markTracking);
    };
  }, [step, active, reduced, layer, spot, bubble, arrow]);

  return found.stepId === step.id ? found.status : "searching";
}
