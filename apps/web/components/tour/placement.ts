import type { TourSide } from "./steps";

export type Box = { left: number; top: number; width: number; height: number; right: number; bottom: number };
export type Size = { width: number; height: number };
export type Dock = "top" | "bottom";

export const SHEET_BREAKPOINT = 640;
const GAP = 16;
const MARGIN = 12;
const ARROW_MIN = 18;
const ARROW_SIZE = 14;

export type Placement = {
  side: TourSide | "sheet";
  x: number;
  y: number;
  /** Offset of the arrow along the bubble edge facing the target; null for a sheet. */
  arrow: number | null;
};

type PlaceInput = {
  target: Box;
  bubble: Size;
  viewport: Size;
  preferred: TourSide;
  /** Height of the fixed nav (and banner) the bubble should not tuck under. */
  headerHeight: number;
};

const FLIP_ORDER: Record<TourSide, readonly TourSide[]> = {
  bottom: ["top", "right", "left"],
  top: ["bottom", "right", "left"],
  right: ["left", "bottom", "top"],
  left: ["right", "bottom", "top"],
};

const clampTo = (value: number, min: number, max: number) => Math.min(Math.max(min, value), Math.max(min, max));

/** Where the bubble goes: the preferred side if it fits, else the first side that does, clamped to the screen. */
export function placeBubble({ target, bubble, viewport, preferred, headerHeight }: PlaceInput): Placement {
  if (viewport.width < SHEET_BREAKPOINT) {
    return { side: "sheet", x: (viewport.width - bubble.width) / 2, y: 0, arrow: null };
  }

  const fits: Record<TourSide, boolean> = {
    bottom: target.bottom + GAP + bubble.height + MARGIN <= viewport.height,
    top: target.top - GAP - bubble.height - MARGIN >= headerHeight,
    right: target.right + GAP + bubble.width + MARGIN <= viewport.width,
    left: target.left - GAP - bubble.width - MARGIN >= 0,
  };
  const side = [preferred, ...FLIP_ORDER[preferred]].find((candidate) => fits[candidate]) ?? "bottom";

  let x: number;
  let y: number;
  if (side === "bottom" || side === "top") {
    x = target.left + target.width / 2 - bubble.width / 2;
    y = side === "bottom" ? target.bottom + GAP : target.top - GAP - bubble.height;
  } else {
    y = target.top + target.height / 2 - bubble.height / 2;
    x = side === "right" ? target.right + GAP : target.left - GAP - bubble.width;
  }
  x = clampTo(x, MARGIN, viewport.width - bubble.width - MARGIN);
  y = clampTo(y, MARGIN, viewport.height - bubble.height - MARGIN);

  const arrow =
    side === "bottom" || side === "top"
      ? clampTo(target.left + target.width / 2 - x - ARROW_SIZE / 2, ARROW_MIN, bubble.width - 32)
      : clampTo(target.top + target.height / 2 - y - ARROW_SIZE / 2, ARROW_MIN, bubble.height - 32);
  return { side, x, y, arrow };
}

/** The sheet goes on the half of the screen the target is not in. */
export function sheetDockFor(target: Box, viewportHeight: number): Dock {
  return target.top + target.height / 2 > viewportHeight / 2 ? "top" : "bottom";
}

export function overlapsSheet(target: Box, dock: Dock, sheetHeight: number, viewportHeight: number, headerHeight: number): boolean {
  if (dock === "bottom") return target.bottom > viewportHeight - sheetHeight - MARGIN;
  return target.top < headerHeight + sheetHeight + MARGIN;
}
