"use client";

import { useEffect, useRef } from "react";

import { subscribeFrames } from "@/components/signature/frame-loop";
import { useReducedMotion } from "@/components/signature/reduced-motion";

import { buildPitch, pitchProjector, sweepGlow, sweepX } from "./pitch";

const FRAME_INTERVAL_MS = 50;
const ANIMATION_START_DELAY_MS = 3000;
// The digits are faint decoration, so a 1x backing store keeps software-rasterised phones fast.
const MAX_DPR = 1;

/**
 * A FIFA pitch drawn as green digits with a pale sweep travelling along it and a slow camera
 * drift. Under reduced motion it paints one still frame and never subscribes to the frame loop.
 */
export default function DataPitchCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const reducedMotion = useReducedMotion(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    const host = canvas?.parentElement;
    if (!canvas || !context || !host) return;

    const { lines, field } = buildPitch();
    const startedAt = performance.now();
    let width = 0;
    let height = 0;
    let dpr = 1;
    let visible = true;
    let lastDrawn = 0;
    let monoFamily = "monospace";
    const readFont = () => {
      monoFamily = getComputedStyle(canvas).getPropertyValue("--font-mono").trim() || "monospace";
    };

    const draw = (now: number) => {
      const elapsedSeconds = reducedMotion ? 0 : (now - startedAt) / 1000;
      const camera = { width, height, elapsedSeconds, drifting: !reducedMotion };
      const project = pitchProjector(camera);
      const sweep = reducedMotion ? null : sweepX(elapsedSeconds);

      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      context.clearRect(0, 0, width, height);

      for (const point of field) {
        const { x, y, scale } = project(point);
        context.fillStyle = `rgb(34 197 94 / ${0.09 * scale})`;
        context.fillRect(x, y, 1.2 * scale, 1.2 * scale);
      }

      context.textAlign = "center";
      context.textBaseline = "middle";
      let currentSize = 0;
      for (const point of lines) {
        const { x, y, scale } = project(point);
        const glow = sweepGlow(point.x, sweep);
        const alpha = Math.min(1, 0.24 + 0.3 * (scale - 0.7) + glow * 0.65);
        context.fillStyle = `rgb(${Math.round(34 + 186 * glow)} ${Math.round(197 + 55 * glow)} ${Math.round(94 + 137 * glow)} / ${alpha})`;
        if (point.spot) {
          context.beginPath();
          context.arc(x, y, 2.2 * scale, 0, Math.PI * 2);
          context.fill();
          continue;
        }
        const size = Math.max(5, Math.round(9.5 * scale * 2) / 2);
        if (size !== currentSize) {
          currentSize = size;
          context.font = `500 ${size}px ${monoFamily}`;
        }
        context.fillText(point.glyph, x, y);
      }
    };

    const resize = () => {
      const box = host.getBoundingClientRect();
      width = box.width;
      height = box.height;
      dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      draw(performance.now());
    };

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(host);
    resize();
    readFont();
    document.fonts?.ready.then(() => {
      readFont();
      draw(performance.now());
    });

    if (reducedMotion) return () => resizeObserver.disconnect();

    const visibilityObserver = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
    });
    visibilityObserver.observe(host);
    let unsubscribe = () => {};
    // The still frame is already painted; animating waits until the page has settled so it never competes with hydration.
    const startTimer = setTimeout(() => {
      unsubscribe = subscribeFrames((now) => {
        if (!visible || now - lastDrawn < FRAME_INTERVAL_MS) return;
        lastDrawn = now;
        draw(now);
      });
    }, ANIMATION_START_DELAY_MS);

    return () => {
      clearTimeout(startTimer);
      unsubscribe();
      visibilityObserver.disconnect();
      resizeObserver.disconnect();
    };
  }, [reducedMotion]);

  return <canvas ref={canvasRef} aria-hidden="true" className="absolute inset-0 -z-20 size-full" />;
}
