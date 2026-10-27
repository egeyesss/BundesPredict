import type { ReactNode } from "react";

export type Tile = { label: string; value: string; context: ReactNode; tour?: string };

export function Tiles({ tiles }: { tiles: Tile[] }) {
  return (
    <dl className="grid grid-cols-4 gap-3 max-[900px]:grid-cols-2 max-[480px]:grid-cols-1">
      {tiles.map((tile) => (
        <div key={tile.label} data-tour={tile.tour} className="grid content-start gap-1.5 rounded-xl border border-bp-border bg-bp-surface-1 p-[18px]">
          <dt className="text-[13px] text-bp-text-muted">{tile.label}</dt>
          <dd className="grid gap-1.5">
            <strong className="font-display text-[40px] leading-none font-bold tabular-nums">{tile.value}</strong>
            <span className="font-mono text-xs text-bp-text-muted [&_b]:font-medium [&_b]:text-bp-text">{tile.context}</span>
          </dd>
        </div>
      ))}
    </dl>
  );
}
