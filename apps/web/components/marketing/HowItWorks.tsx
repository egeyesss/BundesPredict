import { Section, SectionHead } from "./Section";

const PANELS = [
  {
    tag: "Model",
    title: "A fitted score grid",
    body: (
      <>
        A Dixon-Coles model rates every team&apos;s attack and defence from Bundesliga results since 2020/21 and is refit daily.
        Each fixture becomes one grid of scoreline chances, so win, draw, loss and goal markets always agree.
      </>
    ),
  },
  {
    tag: "Agent",
    title: "Small, capped nudges",
    body: (
      <>
        The agent reads your news, checks it with squad, form and weather tools, and asks for expected-goals changes. It has no way
        to set a probability, and each change is capped at{" "}
        <code className="rounded-sm bg-bp-surface-2 px-1.5 py-px font-mono text-[13px] text-bp-text">±0.60 xG</code>.
      </>
    ),
  },
  {
    tag: "Audit trail",
    title: "Every answer shows its work",
    body: (
      <>
        You see the model&apos;s probabilities beside the adjusted ones, what each adjustment asked for, and where the cap cut it
        down. Every prediction is stored with the exact model run behind it.
      </>
    ),
  },
] as const;

export function HowItWorks() {
  return (
    <Section id="how" name="How it works">
      <SectionHead id="how" eyebrow="How it works" title="The model does the maths. The agent does the words." />
      <div className="grid overflow-hidden rounded-xl border border-bp-border min-[861px]:grid-cols-3">
        {PANELS.map((panel) => (
          <div
            key={panel.tag}
            className="grid content-start gap-3 border-b border-bp-border p-6 last:border-b-0 min-[861px]:border-r min-[861px]:border-b-0 min-[861px]:last:border-r-0"
          >
            <span className="font-mono text-xs text-bp-red-text">{panel.tag}</span>
            <h3 className="m-0 font-display text-[22px] leading-[1.15] font-semibold tracking-[0.02em]">{panel.title}</h3>
            <p className="m-0 text-[15px] text-bp-text-muted">{panel.body}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}
