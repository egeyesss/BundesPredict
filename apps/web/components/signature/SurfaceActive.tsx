"use client";

import { createContext, useContext, type ReactNode } from "react";

const SurfaceActiveContext = createContext(true);

/**
 * Marks whether the surface hosting its children is the visible one. The island
 * renders its logo in four crossfading layers; only the visible layer should run
 * a canvas.
 */
export function SurfaceActive({ active, children }: { active: boolean; children: ReactNode }) {
  return <SurfaceActiveContext.Provider value={active}>{children}</SurfaceActiveContext.Provider>;
}

export function useSurfaceActive(): boolean {
  return useContext(SurfaceActiveContext);
}
