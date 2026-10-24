"use client";

import { useEffect, useState, type ReactNode } from "react";

import { SurfaceActive } from "./SurfaceActive";

/**
 * Keeps every canvas below it idle until the page has loaded and a moment has passed, so the
 * wordmark rain starts after hydration instead of competing with it. The text underneath is
 * already the final look, so nothing jumps when the canvases appear.
 */
export function DeferredSurface({ children, delayMs = 2500 }: { children: ReactNode; delayMs?: number }) {
  const [settled, setSettled] = useState(false);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const arm = () => {
      timer = setTimeout(() => setSettled(true), delayMs);
    };
    if (document.readyState === "complete") arm();
    else window.addEventListener("load", arm, { once: true });
    return () => {
      clearTimeout(timer);
      window.removeEventListener("load", arm);
    };
  }, [delayMs]);

  return <SurfaceActive active={settled}>{children}</SurfaceActive>;
}
