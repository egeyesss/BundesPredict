"use client";

import { useEffect } from "react";

import { useIslandActivity } from "@/components/brand/IslandActivity";

const SECTION_SELECTOR = "[data-landing-section]";
const DEFAULT_NAME = "Top";

/** Tells the island which landing section is under the middle of the viewport. */
export function SectionObserver() {
  const { setSectionName } = useIslandActivity();

  useEffect(() => {
    setSectionName(DEFAULT_NAME);
    const sections = document.querySelectorAll<HTMLElement>(SECTION_SELECTOR);
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setSectionName((entry.target as HTMLElement).dataset.landingSection ?? DEFAULT_NAME);
        }
      },
      { rootMargin: "-45% 0px -50% 0px" },
    );
    sections.forEach((section) => observer.observe(section));
    return () => {
      observer.disconnect();
      setSectionName(null);
    };
  }, [setSectionName]);

  return null;
}
