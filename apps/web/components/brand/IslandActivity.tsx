"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type IslandActivity = {
  /** Set while the agent streams; the island swaps the page name for this caption. */
  agentCaption: string | null;
  setAgentCaption: (caption: string | null) => void;
  /** The landing page's current section, shown in place of the page name while it is set. */
  sectionName: string | null;
  setSectionName: (name: string | null) => void;
};

const IslandActivityContext = createContext<IslandActivity>({
  agentCaption: null,
  setAgentCaption: () => {},
  sectionName: null,
  setSectionName: () => {},
});

export function IslandActivityProvider({ children }: { children: ReactNode }) {
  const [agentCaption, setAgentCaption] = useState<string | null>(null);
  const [sectionName, setSectionName] = useState<string | null>(null);
  const value = useMemo(
    () => ({ agentCaption, setAgentCaption, sectionName, setSectionName }),
    [agentCaption, sectionName],
  );
  return <IslandActivityContext.Provider value={value}>{children}</IslandActivityContext.Provider>;
}

export function useIslandActivity(): IslandActivity {
  return useContext(IslandActivityContext);
}
