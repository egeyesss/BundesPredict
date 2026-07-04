export interface Stage {
  label: string;
  done: boolean;
  ok: boolean;
}

/** The live progress readout while the agent works, one line per tool call. */
export default function StageList({
  stages,
  pending,
}: {
  stages: Stage[];
  pending: boolean;
}) {
  return (
    <ul className="space-y-1.5 text-xs text-zinc-500 dark:text-zinc-400">
      {stages.map((stage, i) => (
        <li key={i} className="flex items-center gap-2">
          {!stage.done ? (
            <span className="h-3 w-3 shrink-0 animate-spin rounded-full border border-zinc-300 border-t-zinc-600 dark:border-zinc-600 dark:border-t-zinc-300" />
          ) : stage.ok ? (
            <span className="text-emerald-600 dark:text-emerald-400">✓</span>
          ) : (
            <span className="text-amber-600 dark:text-amber-400">!</span>
          )}
          <span>
            {stage.label}
            {stage.done && !stage.ok && " — retrying"}
          </span>
        </li>
      ))}
      {stages.length === 0 && pending && (
        <li className="flex items-center gap-2">
          <span className="h-3 w-3 shrink-0 animate-spin rounded-full border border-zinc-300 border-t-zinc-600 dark:border-zinc-600 dark:border-t-zinc-300" />
          <span>Thinking…</span>
        </li>
      )}
      {stages.length > 0 && stages.every((s) => s.done) && pending && (
        <li className="flex items-center gap-2">
          <span className="h-3 w-3 shrink-0 animate-spin rounded-full border border-zinc-300 border-t-zinc-600 dark:border-zinc-600 dark:border-t-zinc-300" />
          <span>Writing the explanation…</span>
        </li>
      )}
    </ul>
  );
}
