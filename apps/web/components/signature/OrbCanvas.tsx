"use client";

import { useEffect, useRef, useState } from "react";

import type { OrbState } from "@/lib/agent-state";

import { subscribeFrames } from "./frame-loop";
import { OrbEngine } from "./orb-engine";
import { OrbFallback } from "./OrbFallback";
import { useReducedMotion } from "./reduced-motion";

function canvas2dSupported() {
  return document.createElement("canvas").getContext("2d") !== null;
}

/** The canvas half of the orb. Loaded lazily and client-only by AgentOrb. */
export default function OrbCanvas({ state }: { state: OrbState }) {
  const reducedMotion = useReducedMotion(false);
  const [supported] = useState(canvas2dSupported);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const engineRef = useRef<OrbEngine | null>(null);
  const stateRef = useRef(state);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!supported || !canvas) return;

    const engine = new OrbEngine(canvas);
    engineRef.current = engine;
    engine.setState(stateRef.current, performance.now());

    const drawStill = () => {
      engine.snap();
      engine.draw(performance.now());
    };

    let visible = true;
    const resizeObserver = new ResizeObserver(([entry]) => {
      engine.resize(entry.contentRect.width);
      if (reducedMotion) drawStill();
      else engine.draw(performance.now());
    });
    resizeObserver.observe(canvas);

    const intersectionObserver =
      typeof IntersectionObserver === "undefined"
        ? null
        : new IntersectionObserver(([entry]) => {
            visible = entry.isIntersecting;
          });
    intersectionObserver?.observe(canvas);

    let stopFrames = () => {};
    if (reducedMotion) {
      document.fonts.addEventListener("loadingdone", drawStill);
      stopFrames = () => document.fonts.removeEventListener("loadingdone", drawStill);
    } else {
      stopFrames = subscribeFrames((now, deltaMs) => {
        engine.step(deltaMs / 1000);
        if (visible) engine.draw(now);
      });
    }

    return () => {
      stopFrames();
      resizeObserver.disconnect();
      intersectionObserver?.disconnect();
      engineRef.current = null;
    };
  }, [supported, reducedMotion]);

  useEffect(() => {
    stateRef.current = state;
    const engine = engineRef.current;
    if (!engine) return;
    engine.setState(state, performance.now());
    if (reducedMotion) {
      engine.snap();
      engine.draw(performance.now());
    }
  }, [state, reducedMotion]);

  if (!supported) return <OrbFallback />;
  return <canvas ref={canvasRef} className="block size-full" />;
}
