import type { ReactNode } from "react";

type BoxProps = {
  x: number;
  y: number;
  width: number;
  height: number;
  title: string;
  lines?: readonly string[];
  tone?: "default" | "model" | "external";
};

const TONE_STROKE = {
  default: "stroke-bp-border",
  model: "stroke-bp-red",
  external: "stroke-bp-border",
} as const;

function Box({ x, y, width, height, title, lines = [], tone = "default" }: BoxProps) {
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        rx={10}
        strokeWidth={tone === "model" ? 1.5 : 1}
        strokeDasharray={tone === "external" ? "5 4" : undefined}
        className={`fill-bp-surface-1 ${TONE_STROKE[tone]}`}
      />
      <text x={x + 14} y={y + 26} className="fill-bp-text font-display text-[19px] font-semibold tracking-[0.02em]">
        {title}
      </text>
      {lines.map((line, index) => (
        <text key={line} x={x + 14} y={y + 50 + index * 20} className="fill-bp-text-muted font-mono text-[12px]">
          {line}
        </text>
      ))}
    </g>
  );
}

function Arrow({ d, label, labelX, labelY }: { d: string; label?: string; labelX?: number; labelY?: number }) {
  return (
    <g>
      <path d={d} fill="none" strokeWidth={1.5} className="stroke-bp-text-muted" markerEnd="url(#arrowhead)" />
      {label && (
        <text x={labelX} y={labelY} textAnchor="middle" className="fill-bp-text-muted font-mono text-[11px]">
          {label}
        </text>
      )}
    </g>
  );
}

function Defs() {
  return (
    <defs>
      <marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" className="fill-bp-text-muted" />
      </marker>
    </defs>
  );
}

const DESCRIPTION =
  "The browser talks to a Next.js app on Vercel. Next.js proxies API calls to a Django service on Railway. Django imports a pure Python model library and stores everything in Postgres on Neon. Stripe sends signed webhooks to Django, the agent calls the Anthropic API, and scheduled GitHub Actions run Django management commands against the database.";

function Frame({ children, className, viewBox }: { children: ReactNode; className: string; viewBox: string }) {
  return (
    <svg role="img" aria-labelledby="arch-title arch-desc" viewBox={viewBox} className={className}>
      <title id="arch-title">BundesPredict architecture</title>
      <desc id="arch-desc">{DESCRIPTION}</desc>
      <Defs />
      {children}
    </svg>
  );
}

/**
 * The system as boxes and arrows. A wide drawing from 700px up and a tall one below that, so the
 * labels stay readable on a phone instead of shrinking with the viewBox.
 */
export function ArchitectureDiagram() {
  return (
    <>
      <Frame viewBox="0 0 1000 540" className="hidden h-auto w-full min-[700px]:block">
        <Box x={450} y={10} width={250} height={64} title="Stripe" lines={["checkout, signed webhooks"]} tone="external" />
        <Box x={760} y={10} width={230} height={64} title="Anthropic API" lines={["the agent's language model"]} tone="external" />

        <Box x={10} y={175} width={130} height={90} title="Browser" lines={["one origin", "session cookie"]} />
        <Box x={190} y={140} width={200} height={160} title="Next.js on Vercel" lines={["Server Components", "proxy.ts rewrites /api/*", "adds the proxy secret", "knows who you are"]} />
        <Box
          x={450}
          y={120}
          width={250}
          height={240}
          title="Django + DRF on Railway"
          lines={["football   predictions", "accounts   chat", "billing    track_record", "notifications   ops", "owns plan and quota", "owns every migration"]}
        />
        <Box
          x={760}
          y={140}
          width={230}
          height={200}
          title="packages/model"
          lines={["model: Dixon-Coles", "agent: tool loop", "eval: backtest", "data: parsers", "never imports Django"]}
          tone="model"
        />
        <Box x={450} y={430} width={250} height={84} title="Postgres on Neon" lines={["Django migrations", "own every table"]} />
        <Box x={190} y={430} width={200} height={84} title="GitHub Actions" lines={["scheduled manage.py", "runs: refit, resolve"]} tone="external" />

        <Arrow d="M140 220 H190" />
        <Arrow d="M390 220 H450" label="/api/*" labelX={420} labelY={208} />
        <Arrow d="M700 220 H760" label="imports" labelX={730} labelY={208} />
        <Arrow d="M575 74 V120" />
        <Arrow d="M875 140 V74" label="tool calls" labelX={915} labelY={110} />
        <Arrow d="M575 360 V430" />
        <Arrow d="M390 472 H450" />
      </Frame>

      <Frame viewBox="0 0 360 780" className="h-auto w-full max-w-[420px] min-[700px]:hidden">
        <Box x={10} y={10} width={340} height={64} title="Browser" lines={["one origin, session cookie"]} />
        <Arrow d="M180 74 V102" />
        <Box x={10} y={102} width={340} height={90} title="Next.js on Vercel" lines={["proxy.ts rewrites /api/*", "and adds the proxy secret"]} />
        <Arrow d="M180 192 V220" />
        <Box x={10} y={220} width={340} height={130} title="Django + DRF on Railway" lines={["football predictions accounts chat", "billing track_record notifications", "owns plan, quota and migrations"]} />
        <Arrow d="M180 350 V378" label="imports" labelX={222} labelY={368} />
        <Box x={10} y={378} width={340} height={110} title="packages/model" lines={["Dixon-Coles engine, agent loop,", "backtest, data parsers", "never imports Django"]} tone="model" />
        <Box x={10} y={518} width={340} height={64} title="Postgres on Neon" lines={["Django migrations own every table"]} />
        <Box x={10} y={602} width={340} height={64} title="Stripe" lines={["signed webhooks into Django"]} tone="external" />
        <Box x={10} y={686} width={340} height={64} title="Anthropic API" lines={["called by the agent for language"]} tone="external" />
      </Frame>
    </>
  );
}
