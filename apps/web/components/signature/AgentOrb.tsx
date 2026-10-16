"use client";

import dynamic from "next/dynamic";

import type { OrbState } from "@/lib/agent-state";
import { cn } from "@/lib/utils";

import "./orb.css";
import { ORB_SETTINGS, type OrbSizeName } from "./orb-sphere";
import { OrbFallback } from "./OrbFallback";
import { useReducedMotion } from "./reduced-motion";

const OrbCanvas = dynamic(() => import("./OrbCanvas"), { ssr: false, loading: () => <OrbFallback /> });

export type AgentOrbProps = {
  state: OrbState;
  /** A named slot (24, 56 or 280px) or an exact pixel size. */
  size?: OrbSizeName | number;
  className?: string;
};

/**
 * A sphere of digit glyphs that shows what the agent is doing. Decorative: pair it
 * with an AgentCaption, which carries the same progress for screen readers.
 */
export function AgentOrb({ state, size = "message", className }: AgentOrbProps) {
  const reducedMotion = useReducedMotion(false);
  const pixels = typeof size === "number" ? size : ORB_SETTINGS.sizes[size];

  return (
    <span
      data-orb
      aria-hidden="true"
      data-orb-state={state.phase}
      data-orb-tool={state.phase === "tool" ? state.tool : undefined}
      data-reduced={reducedMotion}
      className={cn("orb", className)}
      style={{ width: pixels, height: pixels }}
    >
      <OrbCanvas state={state} />
    </span>
  );
}
