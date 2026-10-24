"use client";

import { createContext, useContext, type ReactNode } from "react";

const SurfaceActiveContext = createContext(true);

/**
 * Marks whether the surface hosting its children is the visible one. The island
 * renders its logo in four crossfading layers; only the visible layer should run
 * a canvas. Nested surfaces are active only while every surface around them is.
 */
export function SurfaceActive({ active, children }: { active: boolean; children: ReactNode }) {
  const outerActive = useContext(SurfaceActiveContext);
  return <SurfaceActiveContext.Provider value={outerActive && active}>{children}</SurfaceActiveContext.Provider>;
}

export function useSurfaceActive(): boolean {
  return useContext(SurfaceActiveContext);
}
