import { IslandNav } from "@/components/brand/IslandNav";
import type { NavUser } from "@/components/brand/nav";
import { WordmarkPlaceholder } from "@/components/brand/WordmarkPlaceholder";
import { IslandActivityProvider } from "@/components/brand/IslandActivity";
import type { IslandMode } from "@/lib/island";

const MODES: readonly IslandMode[] = ["full", "compact", "mobile", "open"];

const FREE_USER: NavUser = { name: "Ege", email: "ege@example.com", plan: "free", chatsUsed: 1, chatsLimit: 3, isDemo: false };
const PRO_USER: NavUser = { name: "Ege", email: "ege@example.com", plan: "pro", chatsUsed: 12, chatsLimit: 100, isDemo: false };

function Preview({ mode, user, audience }: { mode: IslandMode; user: NavUser | null; audience: string }) {
  return (
    <div className="grid content-start gap-2">
      <h3 className="font-mono text-xs tracking-wider text-bp-text-muted uppercase">
        {audience} · {mode}
      </h3>
      <div
        role="group"
        aria-label={`${audience} ${mode} island, scrollable`}
        tabIndex={0}
        className="overflow-x-auto rounded-xl border border-bp-border bg-bp-bg p-4"
      >
        <IslandNav
          wordmark={<WordmarkPlaceholder />}
          user={user}
          preview={{ mode, label: `Island preview, ${audience}, ${mode}` }}
        />
      </div>
    </div>
  );
}

export function IslandPreviews() {
  return (
    <IslandActivityProvider>
      <div className="grid gap-6">
        {MODES.map((mode) => (
          <Preview key={`out-${mode}`} mode={mode} user={null} audience="Signed out" />
        ))}
        {MODES.map((mode) => (
          <Preview key={`free-${mode}`} mode={mode} user={FREE_USER} audience="Free plan" />
        ))}
        <Preview mode="full" user={PRO_USER} audience="Pro plan" />
        <Preview mode="open" user={PRO_USER} audience="Pro plan" />
      </div>
    </IslandActivityProvider>
  );
}
