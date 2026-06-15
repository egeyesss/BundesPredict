// Placeholder chat page for now. The actual messages, probability bars, score
// heatmap and adjustments panel get wired up to the API later.

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 dark:bg-black">
      <main className="flex w-full max-w-2xl flex-1 flex-col px-4">
        <header className="border-b border-black/10 py-6 dark:border-white/10">
          <h1 className="text-2xl font-semibold tracking-tight text-black dark:text-zinc-50">
            BundesPredict
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Calibrated Bundesliga predictions with explainable, bounded context
            adjustments.
          </p>
        </header>

        <section className="flex flex-1 flex-col items-center justify-center text-center text-zinc-400">
          <p className="text-sm">
            Chat not wired up yet — try{" "}
            <span className="font-medium text-zinc-500 dark:text-zinc-300">
              &ldquo;Predict Dortmund vs Leipzig Saturday&rdquo;
            </span>
          </p>
        </section>

        <div className="py-6">
          <input
            type="text"
            disabled
            placeholder="Ask about a fixture…"
            className="w-full rounded-full border border-black/10 bg-white px-5 py-3 text-sm text-zinc-900 outline-none disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:bg-zinc-900 dark:text-zinc-100"
          />
        </div>
      </main>
    </div>
  );
}
