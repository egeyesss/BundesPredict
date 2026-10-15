import { readFileSync } from "node:fs";
import path from "node:path";

type Token = { name: string; value: string };

function readTokens(): Token[] {
  const css = readFileSync(path.join(process.cwd(), "app/styles/tokens.css"), "utf8");
  return [...css.matchAll(/^\s*(--[\w-]+):\s*([^;]+);/gm)]
    .map(([, name, value]) => ({ name, value: value.trim() }))
    .filter(({ name }) => name !== "--color-scheme");
}

export function TokenSwatches() {
  const tokens = readTokens();

  return (
    <ul className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-3">
      {tokens.map(({ name, value }) => {
        const isRadius = name.includes("radius");
        return (
          <li key={name} data-token={name} className="grid gap-3 rounded-lg border border-bp-border bg-bp-surface-1 p-3">
            <span
              aria-hidden="true"
              className="h-14 border border-white/10"
              style={
                isRadius
                  ? { width: 56, borderRadius: `var(${name})`, background: "var(--bp-surface-2)" }
                  : { background: `var(${name})`, borderRadius: 6 }
              }
            />
            <span className="grid gap-0.5 font-mono text-xs">
              <span className="text-bp-text">{name}</span>
              <span className="text-bp-text-muted">{value}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
