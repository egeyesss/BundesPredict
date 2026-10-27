"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";

import { findAnchor } from "./anchors";
import { STEPS } from "./steps";

import "./tour.css";

const subscribeNever = () => () => {};

const SIZE = 22;
const EDGE = 4;
const REFRESH_MS = 1000;

type Spot = { index: number; left: number; top: number };

const sameSpots = (a: readonly Spot[], b: readonly Spot[]) =>
  a.length === b.length && a.every((spot, i) => spot.index === b[i].index && spot.left === b[i].left && spot.top === b[i].top);

/** The part of the element a viewer can actually see, once its scrolling parents and the window clip it. */
function visibleRect(element: HTMLElement): DOMRect | null {
  const rect = element.getBoundingClientRect();
  let top = Math.max(rect.top, 0);
  let bottom = Math.min(rect.bottom, window.innerHeight);
  for (let parent = element.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
    const { overflowY } = getComputedStyle(parent);
    if (overflowY !== "auto" && overflowY !== "scroll") continue;
    const box = parent.getBoundingClientRect();
    top = Math.max(top, box.top);
    bottom = Math.min(bottom, box.bottom);
  }
  return bottom - top < 1 ? null : rect;
}

function measure(): Spot[] {
  const spots: Spot[] = [];
  STEPS.forEach((step, index) => {
    if (step.hotspot === false) return;
    const element = findAnchor([step.anchors[0]]);
    const rect = element && visibleRect(element);
    if (!rect) return;
    spots.push({
      index,
      left: Math.round(Math.min(Math.max(rect.right - SIZE / 2 - 2, EDGE), window.innerWidth - SIZE - EDGE)),
      top: Math.round(rect.top - 9),
    });
  });
  return spots;
}

/** A "?" on every anchored element of the current page; each opens that one stop. */
export function Hotspots({ onOpen }: { onOpen: (index: number) => void }) {
  const pathname = usePathname();
  const [spots, setSpots] = useState<Spot[]>([]);
  const mounted = useSyncExternalStore(subscribeNever, () => true, () => false);

  useEffect(() => {
    let frame = 0;
    const refresh = () => {
      frame = 0;
      const next = measure();
      setSpots((previous) => (sameSpots(previous, next) ? previous : next));
    };
    const schedule = () => {
      if (frame === 0) frame = requestAnimationFrame(refresh);
    };
    schedule();
    window.addEventListener("scroll", schedule, { passive: true, capture: true });
    window.addEventListener("resize", schedule);
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList: true, subtree: true });
    const interval = setInterval(schedule, REFRESH_MS);
    return () => {
      cancelAnimationFrame(frame);
      clearInterval(interval);
      observer.disconnect();
      window.removeEventListener("scroll", schedule, { capture: true });
      window.removeEventListener("resize", schedule);
    };
  }, [pathname]);

  if (!mounted) return null;
  return createPortal(
    <div className="tour-hotspots" data-tour-hotspots>
      {spots.map(({ index, left, top }) => (
        <button
          key={STEPS[index].id}
          type="button"
          className="tour-hotspot"
          data-tour-hotspot={STEPS[index].id}
          aria-label={`Explain: ${STEPS[index].title}`}
          style={{ left, top }}
          onClick={() => onOpen(index)}
        >
          ?
        </button>
      ))}
    </div>,
    document.body,
  );
}
