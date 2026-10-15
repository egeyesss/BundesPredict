const ROLES = [
  {
    role: "Display",
    face: "Barlow Condensed 600/700",
    use: "matchday headers, scores, big percentages, club codes",
    sample: <span className="font-display text-5xl leading-none font-bold tracking-wide">MATCHDAY 7</span>,
  },
  {
    role: "Display, numbers",
    face: "Barlow Condensed 700, tabular",
    use: "probabilities that update in place",
    sample: <span className="font-display text-5xl leading-none font-bold tabular-nums">64% 19% 17%</span>,
  },
  {
    role: "UI and body",
    face: "Inter 400/500/600",
    use: "everything readable",
    sample: <span className="text-base">Bayern are 64% to win at home, with the draw at 19%.</span>,
  },
  {
    role: "Model voice",
    face: "JetBrains Mono 400/500",
    use: "agent stages, adjustment chips, rain glyphs",
    sample: <span className="font-mono text-sm">predict_with_adjustments · xG 2.61 – 1.14</span>,
  },
] as const;

export function TypeRoles() {
  return (
    <div className="grid gap-3">
      {ROLES.map(({ role, face, use, sample }) => (
        <div key={role} className="grid gap-3 rounded-lg border border-bp-border bg-bp-surface-1 p-4 md:grid-cols-[220px_1fr] md:items-center">
          <div className="grid gap-1">
            <h3 className="font-display text-xl font-semibold">{role}</h3>
            <p className="font-mono text-xs text-bp-text-muted">{face}</p>
            <p className="text-xs text-bp-text-muted">{use}</p>
          </div>
          <div className="min-w-0 break-words">{sample}</div>
        </div>
      ))}
    </div>
  );
}
