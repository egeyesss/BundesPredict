"use client";

// The chat page: ask about a fixture in plain language, watch the agent work
// (staged progress from the SSE stream), then get the full answer — baseline
// vs adjusted odds, the applied adjustments, the scoreline heatmap, markets.

import { useEffect, useRef, useState } from "react";

import { streamPredict, type PredictResponse, type StageEvent } from "@/lib/api";
import ResultCard from "./components/ResultCard";
import StageList, { type Stage } from "./components/StageList";

interface UserMessage {
  role: "user";
  text: string;
}

interface AssistantMessage {
  role: "assistant";
  stages: Stage[];
  result: PredictResponse | null;
  error: string | null;
  pending: boolean;
}

type Message = UserMessage | AssistantMessage;

const SUGGESTIONS = [
  "Predict Borussia Dortmund vs RB Leipzig",
  "Bayern vs Leverkusen — Kane is out injured and it's stormy",
  "How do Stuttgart look at home against Frankfurt with their keeper suspended?",
];

function stageLabel(event: StageEvent): string {
  const input = event.input ?? {};
  switch (event.name) {
    case "predict_match":
      return `Computing baseline: ${String(input.home)} vs ${String(input.away)}`;
    case "get_team_form":
      return `Checking recent form: ${String(input.team)}`;
    case "lookup_player":
      return `Looking up ${String(input.name)}`;
    case "predict_match_with_context": {
      const n = Array.isArray(input.adjustments) ? input.adjustments.length : 0;
      return `Applying ${n} adjustment${n === 1 ? "" : "s"} and re-running`;
    }
    default:
      return event.name;
  }
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // All stream callbacks mutate only the trailing assistant message.
  function updateAssistant(update: (m: AssistantMessage) => AssistantMessage) {
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last === undefined || last.role !== "assistant") return prev;
      return [...prev.slice(0, -1), update(last)];
    });
  }

  function onStage(event: StageEvent) {
    updateAssistant((m) => {
      if (event.type === "tool_call") {
        return {
          ...m,
          stages: [...m.stages, { label: stageLabel(event), done: false, ok: true }],
        };
      }
      // tool_result: close out the matching in-flight stage.
      const stages = [...m.stages];
      const open = stages.findLastIndex((s) => !s.done);
      if (open !== -1) {
        stages[open] = { ...stages[open], done: true, ok: event.ok ?? true };
      }
      return { ...m, stages };
    });
  }

  async function submit(query: string) {
    const trimmed = query.trim();
    if (trimmed === "" || pending) return;

    setInput("");
    setPending(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", text: trimmed },
      { role: "assistant", stages: [], result: null, error: null, pending: true },
    ]);

    await streamPredict(trimmed, {
      onStage,
      onResult: (result) =>
        updateAssistant((m) => ({ ...m, result, pending: false })),
      onError: (error) =>
        updateAssistant((m) => ({ ...m, error, pending: false })),
    });

    updateAssistant((m) => ({ ...m, pending: false }));
    setPending(false);
  }

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

        <section className="flex flex-1 flex-col gap-6 py-6">
          {messages.length === 0 && (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
              <p className="text-sm text-zinc-400">
                Ask about any Bundesliga fixture — mention injuries, weather, or
                anything else and the model shows how it moves the odds.
              </p>
              <div className="flex flex-col gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => void submit(s)}
                    className="rounded-full border border-black/10 bg-white px-4 py-2 text-xs text-zinc-600 transition-colors hover:border-black/25 dark:border-white/10 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:border-white/25"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message, i) =>
            message.role === "user" ? (
              <div key={i} className="flex justify-end">
                <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-zinc-900 px-4 py-2.5 text-sm text-zinc-50 dark:bg-zinc-100 dark:text-zinc-900">
                  {message.text}
                </p>
              </div>
            ) : (
              <div
                key={i}
                className="rounded-2xl rounded-bl-sm border border-black/10 bg-white p-4 dark:border-white/10 dark:bg-zinc-950"
              >
                {(message.stages.length > 0 || message.pending) &&
                  message.error === null && (
                    <StageList stages={message.stages} pending={message.pending} />
                  )}
                {message.error !== null && (
                  <p className="text-sm text-red-600 dark:text-red-400">
                    {message.error}
                  </p>
                )}
                {message.result !== null && (
                  <div className={message.stages.length > 0 ? "mt-4" : ""}>
                    <ResultCard result={message.result} />
                  </div>
                )}
              </div>
            ),
          )}
          <div ref={bottomRef} />
        </section>

        <div className="sticky bottom-0 bg-zinc-50 py-4 dark:bg-black">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void submit(input);
            }}
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={pending}
              placeholder={pending ? "Predicting…" : "Ask about a fixture…"}
              className="w-full rounded-full border border-black/10 bg-white px-5 py-3 text-sm text-zinc-900 outline-none transition-colors focus:border-black/30 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-white/30"
            />
          </form>
        </div>
      </main>
    </div>
  );
}
