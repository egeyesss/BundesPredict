const SAMPLE_COUNT = 48;

/**
 * Samples a damped spring (Framer-style bounce and duration) into a CSS
 * `linear()` easing. The curve runs for 1.5 periods so the settle after the
 * overshoot is not cut off.
 */
export function springEasing(bounce: number, durationSeconds: number): { css: string; ms: number } {
  const dampingRatio = 1 - bounce;
  const omega = (2 * Math.PI) / durationSeconds;
  const dampedOmega = omega * Math.sqrt(1 - dampingRatio ** 2);
  const total = durationSeconds * 1.5;

  const points = Array.from({ length: SAMPLE_COUNT + 1 }, (_, index) => {
    const t = (total * index) / SAMPLE_COUNT;
    const envelope = Math.exp(-dampingRatio * omega * t);
    const value =
      bounce > 0
        ? 1 - envelope * (Math.cos(dampedOmega * t) + ((dampingRatio * omega) / dampedOmega) * Math.sin(dampedOmega * t))
        : 1 - envelope * (1 + omega * t);
    return value.toFixed(4);
  });
  points[SAMPLE_COUNT] = "1";

  return { css: `linear(${points.join(", ")})`, ms: Math.round(total * 1000) };
}
