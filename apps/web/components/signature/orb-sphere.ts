export const ORB_SETTINGS = {
  glyphs: "0123456789",
  glyphsAt280px: 380,
  glyphScale: 0.055,
  dotsBelowGlyphPx: 6,
  axisTiltRad: 0.35,
  idleSpinRadPerSec: 0.25,
  thinkingSpinMultiplier: 2,
  thinkingRipple: 0.15,
  toolPulseMs: 700,
  coreGlow: 0.6,
  depthFadeExponent: 1.5,
  stateRampMs: 400,
  doneHoldMs: 1200,
  errorJitterMs: 300,
  sizes: { chatHeader: 24, message: 56, stage: 280 },
} as const;

export type OrbSizeName = keyof typeof ORB_SETTINGS.sizes;
export type OrbPhase = "idle" | "thinking" | "tool" | "done" | "error";

/** What the live values ease toward in each phase. */
export type OrbTarget = { spin: number; ripple: number; glow: number; mutate: number; grey: number };
export type OrbLive = OrbTarget;

export const ORB_TARGETS: Record<OrbPhase, OrbTarget> = {
  idle: { spin: 0, ripple: 0, glow: 0.35, mutate: 0.4, grey: 0 },
  thinking: { spin: 1, ripple: 1, glow: 0.8, mutate: 6, grey: 0 },
  tool: { spin: 1, ripple: 0.6, glow: 1, mutate: 8, grey: 0 },
  done: { spin: 0.3, ripple: 0, glow: 0.6, mutate: 1, grey: 0 },
  error: { spin: 0, ripple: 0, glow: 0.15, mutate: 0.2, grey: 1 },
};

const MIN_POINTS = 48;
const REFERENCE_SIZE = 280;

export const pointCountFor = (cssSize: number) =>
  Math.max(MIN_POINTS, Math.round(ORB_SETTINGS.glyphsAt280px * Math.min(1, Math.sqrt(cssSize / REFERENCE_SIZE))));

export const glyphPxFor = (cssSize: number) => cssSize * ORB_SETTINGS.glyphScale;

/** Glyphs under 6px are unreadable, so small orbs draw plain dots. */
export const usesDots = (cssSize: number) => glyphPxFor(cssSize) < ORB_SETTINGS.dotsBelowGlyphPx;

export type SpherePoint = { x: number; y: number; z: number };

/** Points spread evenly over a unit sphere along a golden-angle spiral. */
export function buildSphere(count: number): SpherePoint[] {
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  return Array.from({ length: count }, (_, index) => {
    const y = 1 - ((index + 0.5) / count) * 2;
    const radius = Math.sqrt(1 - y * y);
    const angle = index * goldenAngle;
    return { x: Math.cos(angle) * radius, y, z: Math.sin(angle) * radius };
  });
}

export const depthAlpha = (depth: number) => 0.08 + 0.92 * Math.pow(depth, ORB_SETTINGS.depthFadeExponent);

export const spinRate = (spin: number) =>
  ORB_SETTINGS.idleSpinRadPerSec * (1 + (ORB_SETTINGS.thinkingSpinMultiplier - 1) * spin);

/** Moves `current` toward `target` by `deltaSeconds / ramp`, clamped so it never overshoots. */
export function easeToward(current: number, target: number, deltaSeconds: number): number {
  const fraction = Math.min(1, deltaSeconds / (ORB_SETTINGS.stateRampMs / 1000));
  return current + (target - current) * fraction;
}
