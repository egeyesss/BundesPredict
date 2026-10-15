"use client";

import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

import "./wordmark.css";
import { useReducedMotion } from "./reduced-motion";
import { useSurfaceActive } from "./SurfaceActive";
import { WordmarkRenderer } from "./wordmark-renderer";

export type WordmarkProps = {
  size?: "nav" | "hero";
  /** True while the agent streams: the rain speeds up and fills in. */
  active?: boolean;
  className?: string;
};

const SIZE_CLASS = {
  nav: "text-[20px]",
  hero: "text-[clamp(56px,12.5vw,140px)]",
} as const;

/**
 * "Bundes" in white and "Predict" in red with code rain inside the letters. The
 * text is real markup (server render, search, screen readers, reduced motion);
 * a canvas is laid over "Predict" on the client and never mounted when motion is
 * reduced or the surface hosting the logo is hidden.
 */
export function Wordmark({ size = "nav", active = false, className }: WordmarkProps) {
  const surfaceActive = useSurfaceActive();
  const reducedMotion = useReducedMotion(true);
  const showCanvas = surfaceActive && !reducedMotion;

  const rootRef = useRef<HTMLSpanElement>(null);
  const predictRef = useRef<HTMLSpanElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<WordmarkRenderer | null>(null);
  const activeRef = useRef(active);

  useEffect(() => {
    activeRef.current = active;
    rendererRef.current?.setActive(active);
  }, [active]);

  useEffect(() => {
    const root = rootRef.current;
    const predict = predictRef.current;
    const canvas = canvasRef.current;
    if (!showCanvas || !root || !predict || !canvas) return;

    let renderer: WordmarkRenderer;
    try {
      renderer = new WordmarkRenderer(predict, canvas, () => root.setAttribute("data-live", "true"));
    } catch {
      return;
    }
    renderer.setActive(activeRef.current);
    renderer.start();
    rendererRef.current = renderer;

    return () => {
      renderer.stop();
      rendererRef.current = null;
      root.removeAttribute("data-live");
    };
  }, [showCanvas]);

  return (
    <span
      ref={rootRef}
      className={cn("wm relative inline-block font-display leading-none font-bold whitespace-nowrap", SIZE_CLASS[size], className)}
      data-size={size}
      data-active={active}
    >
      <span className="text-bp-text">Bundes</span>
      <span ref={predictRef} className="wm-predict relative inline-block leading-none text-bp-red">
        <span data-wordmark-text>Predict</span>
        {showCanvas && <canvas ref={canvasRef} aria-hidden="true" className="pointer-events-none absolute inset-0 size-full" />}
      </span>
    </span>
  );
}
