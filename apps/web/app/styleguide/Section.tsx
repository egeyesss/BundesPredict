import type { ReactNode } from "react";

export function Section({ id, title, note, children }: { id: string; title: string; note?: string; children: ReactNode }) {
  return (
    <section aria-labelledby={`${id}-title`} className="grid gap-5 border-t border-bp-border pt-10">
      <div className="grid gap-2">
        <h2 id={`${id}-title`} className="font-display text-4xl leading-none font-bold tracking-wide">
          {title}
        </h2>
        {note && <p className="max-w-[70ch] text-bp-text-muted">{note}</p>}
      </div>
      {children}
    </section>
  );
}
