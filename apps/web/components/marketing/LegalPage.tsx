import type { ReactNode } from "react";

export const CONTACT_EMAIL = "bundespredict@egeyesilyurt.ca";
export const LEGAL_UPDATED = "October 22, 2026";

export function LegalPage({ title, intro, children }: { title: string; intro: string; children: ReactNode }) {
  return (
    <article className="mx-auto grid w-full max-w-[720px] gap-8 px-[max(16px,env(safe-area-inset-left,0px))] py-[clamp(40px,6vw,80px)]">
      <header className="grid gap-3">
        <h1 className="m-0 font-display text-[clamp(40px,6vw,60px)] leading-none font-bold tracking-[0.01em]">{title}</h1>
        <p className="m-0 text-[17px] text-bp-text-muted">{intro}</p>
        <p className="m-0 font-mono text-xs text-bp-text-muted">Last updated {LEGAL_UPDATED}</p>
      </header>
      <div className="grid gap-8 text-[16px] leading-[1.65] text-bp-text [&_a]:underline [&_a]:underline-offset-4 [&_li]:ml-5 [&_li]:list-disc [&_li]:pl-1 [&_ul]:m-0 [&_ul]:grid [&_ul]:gap-1.5 [&_ul]:p-0">
        {children}
      </div>
    </article>
  );
}

export function LegalSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="grid gap-3">
      <h2 className="m-0 font-display text-[28px] leading-none font-semibold tracking-[0.02em]">{title}</h2>
      {children}
    </section>
  );
}

export function ContactLink() {
  return <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>;
}
