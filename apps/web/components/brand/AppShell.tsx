import type { ReactNode } from "react";

import { ShellWordmark } from "@/components/signature/ShellWordmark";

import { IslandActivityProvider } from "./IslandActivity";
import { SessionIslandNav } from "./SessionIslandNav";
import { SiteFooter } from "./SiteFooter";

type AppShellProps = {
  children: ReactNode;
  /** Shown in the nav and footer; defaults to the animated wordmark. */
  wordmark?: ReactNode;
};

export function AppShell({ children, wordmark = <ShellWordmark /> }: AppShellProps) {
  return (
    <IslandActivityProvider>
      <a
        href="#main"
        className="sr-only focus-visible:not-sr-only focus-visible:fixed focus-visible:top-3 focus-visible:left-3 focus-visible:z-50 focus-visible:rounded-md focus-visible:bg-bp-surface-2 focus-visible:px-3 focus-visible:py-2 focus-visible:text-sm"
      >
        Skip to content
      </a>
      <div className="flex min-h-dvh flex-col">
        <SessionIslandNav wordmark={wordmark} />
        <main id="main" className="flex flex-1 flex-col pt-[76px]">
          {children}
        </main>
        <SiteFooter wordmark={wordmark} />
      </div>
    </IslandActivityProvider>
  );
}
