"use client";

import dynamic from "next/dynamic";

const DataPitchCanvas = dynamic(() => import("./DataPitchCanvas"), { ssr: false });

/** The only canvas hero on the site, loaded after hydration so it never sits on the LCP path. */
export function HeroBackground() {
  return <DataPitchCanvas />;
}
