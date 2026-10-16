"use client";

import { useEffect } from "react";

import type { FixtureCard as Fixture } from "@/lib/api/types";

import { FixtureCard } from "./FixtureCard";

const STAGGER_MS = 40;
const MAX_STAGGER_MS = 300;

let hasEntered = false;

/** Cards rise in once per page load, 40ms apart (300ms at most), and stay still on every later visit. */
export function FixtureGrid({ fixtures, label }: { fixtures: readonly Fixture[]; label: string }) {
  const animate = !hasEntered;

  useEffect(() => {
    hasEntered = true;
  }, []);

  return (
    <ul aria-label={label} className="grid list-none grid-cols-[repeat(auto-fill,minmax(min(100%,300px),1fr))] gap-3 p-0">
      {fixtures.map((fixture, index) => (
        <li key={fixture.id} className="min-w-0">
          <FixtureCard fixture={fixture} enterDelayMs={animate ? Math.min(index * STAGGER_MS, MAX_STAGGER_MS) : undefined} className="h-full" />
        </li>
      ))}
    </ul>
  );
}
