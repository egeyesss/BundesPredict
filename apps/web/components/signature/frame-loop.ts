export type FrameCallback = (now: number, deltaMs: number) => void;

/** A gap longer than this (tab switch, breakpoint) would make the animations jump. */
const MAX_DELTA_MS = 100;

const subscribers = new Set<FrameCallback>();
let handle = 0;
let lastFrame = 0;
let listeningForVisibility = false;

function tick(now: number) {
  handle = 0;
  if (subscribers.size === 0 || document.hidden) return;
  const delta = Math.min(now - lastFrame, MAX_DELTA_MS);
  lastFrame = now;
  for (const callback of [...subscribers]) callback(now, delta);
  schedule();
}

function schedule() {
  if (handle === 0 && subscribers.size > 0 && !document.hidden) handle = requestAnimationFrame(tick);
}

function onVisibilityChange() {
  if (document.hidden) {
    cancelAnimationFrame(handle);
    handle = 0;
    return;
  }
  lastFrame = performance.now();
  schedule();
}

/**
 * One requestAnimationFrame loop shared by every canvas on the page. It runs only
 * while someone is subscribed and the tab is visible.
 */
export function subscribeFrames(callback: FrameCallback): () => void {
  if (!listeningForVisibility) {
    document.addEventListener("visibilitychange", onVisibilityChange);
    listeningForVisibility = true;
  }
  if (subscribers.size === 0) lastFrame = performance.now();
  subscribers.add(callback);
  schedule();

  return () => {
    subscribers.delete(callback);
    if (subscribers.size === 0) {
      cancelAnimationFrame(handle);
      handle = 0;
    }
  };
}
