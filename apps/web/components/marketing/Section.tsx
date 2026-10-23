import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type SectionProps = {
  id: string;
  /** The name the island shows while this section is on screen. */
  name: string;
  children: ReactNode;
  className?: string;
};

export function Section({ id, name, children, className }: SectionProps) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      data-landing-section={name}
      className="border-b border-bp-border px-[max(16px,env(safe-area-inset-left,0px))]"
    >
      <div className={cn("mx-auto grid max-w-[1160px] gap-9 py-[clamp(56px,8vw,96px)]", className)}>{children}</div>
    </section>
  );
}

type SectionHeadProps = {
  id: string;
  eyebrow: string;
  title: string;
  lede?: string;
  centered?: boolean;
};

export function SectionHead({ id, eyebrow, title, lede, centered = false }: SectionHeadProps) {
  return (
    <div className={cn("grid gap-3.5", centered && "justify-items-center text-center")}>
      <span className="font-mono text-xs tracking-[0.08em] text-bp-text-muted uppercase">{eyebrow}</span>
      <h2 id={`${id}-title`} className="m-0 font-display text-[clamp(34px,5vw,52px)] leading-none font-bold tracking-[0.01em] text-balance">
        {title}
      </h2>
      {lede && <p className="m-0 max-w-[60ch] text-[17px] text-bp-text-muted">{lede}</p>}
    </div>
  );
}
