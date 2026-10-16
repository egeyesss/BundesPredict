/** A CSS-only orb for when the canvas is not ready or not available. */
export function OrbFallback() {
  return <span data-orb-fallback aria-hidden="true" className="orb-fallback" />;
}
