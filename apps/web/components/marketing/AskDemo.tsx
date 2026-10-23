"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useIslandActivity } from "@/components/brand/IslandActivity";
import { ClubCrest } from "@/components/brand/ClubCrest";
import { AdjustmentChip } from "@/components/signature/AdjustmentChip";
import { AgentOrb } from "@/components/signature/AgentOrb";
import { ProbabilityBars } from "@/components/signature/ProbabilityBars";
import { useReducedMotion } from "@/components/signature/reduced-motion";
import { StageTicker } from "@/components/signature/StageTicker";
import { Button } from "@/components/ui/button";
import { foldAgentState, useAgentState } from "@/lib/agent-state";
import type { PredictStreamEvent } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { DEMO } from "./demo-content";
import { replayResult, replaySchedule } from "./demo-replay";

const STEPS = [
  { key: "ask", title: "You say what changed", body: "In plain words, about one fixture." },
  { key: "check", title: "The agent checks it", body: "Squad, form and weather lookups, shown as it works." },
  { key: "move", title: "The odds move, with receipts", body: "Model odds next to the new ones, and every adjustment listed." },
] as const;

type StepKey = (typeof STEPS)[number]["key"];

export function AskDemo({ stream }: { stream: readonly PredictStreamEvent[] }) {
  const reducedMotion = useReducedMotion(false);
  const { setAgentCaption } = useIslandActivity();
  const agent = useAgentState();
  const result = useMemo(() => replayResult(stream), [stream]);
  const settled = useMemo(() => foldAgentState(replaySchedule(stream, { instant: true }).map((step) => step.event)), [stream]);

  const [hasRun, setHasRun] = useState(false);
  const [answerShown, setAnswerShown] = useState(true);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const cardRef = useRef<HTMLDivElement>(null);
  const autoPlayed = useRef(false);

  const cancel = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }, []);

  const { dispatch } = agent;
  const play = useCallback(() => {
    cancel();
    setHasRun(true);
    setAnswerShown(false);
    let elapsed = 0;
    for (const step of replaySchedule(stream, { instant: reducedMotion })) {
      elapsed += step.delayMs;
      const apply = () => {
        dispatch(step.event);
        if (step.event.event === "result") setAnswerShown(true);
      };
      if (elapsed === 0) apply();
      else timers.current.push(setTimeout(apply, elapsed));
    }
  }, [cancel, dispatch, reducedMotion, stream]);

  useEffect(() => cancel, [cancel]);

  useEffect(() => {
    const card = cardRef.current;
    if (!card || reducedMotion || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting || autoPlayed.current) return;
        autoPlayed.current = true;
        play();
      },
      { threshold: 0.5 },
    );
    observer.observe(card);
    return () => observer.disconnect();
  }, [play, reducedMotion]);

  const phase = agent.state.phase;
  const working = hasRun && (phase === "thinking" || phase === "tool");
  useEffect(() => {
    setAgentCaption(working ? agent.caption : null);
  }, [agent.caption, setAgentCaption, working]);
  useEffect(() => () => setAgentCaption(null), [setAgentCaption]);

  const stages = hasRun ? agent.stages : settled.stages;
  const caption = working ? agent.caption : `Answered with ${stages.length} steps`;
  const step: StepKey = !hasRun || answerShown ? "move" : phase === "thinking" && stages.length === 0 ? "ask" : "check";

  return (
    <div className="grid items-start gap-9 min-[901px]:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <div className="grid gap-3.5">
        <span className="font-mono text-xs tracking-[0.08em] text-bp-text-muted uppercase">Ask about any fixture</span>
        <h2 id="demo-title" className="m-0 font-display text-[clamp(34px,5vw,52px)] leading-none font-bold tracking-[0.01em] text-balance">
          Bring the news the model hasn&apos;t seen
        </h2>
        <p className="m-0 max-w-[60ch] text-[17px] text-bp-text-muted">
          Lineups, injuries, a storm over the stadium. The agent checks what you said against squad data and the forecast, then
          reruns the model with small, capped changes.
        </p>
        <ol className="m-0 mt-2 grid list-none gap-[18px] p-0">
          {STEPS.map((entry) => (
            <li
              key={entry.key}
              data-active={entry.key === step}
              className="grid gap-1 border-l-2 border-bp-border pl-3.5 data-[active=true]:border-bp-red"
            >
              <b className="font-semibold">{entry.title}</b>
              <span className="text-[15px] text-bp-text-muted">{entry.body}</span>
            </li>
          ))}
        </ol>
      </div>

      <div
        ref={cardRef}
        role="group"
        aria-label="Recorded example"
        className="grid min-w-0 gap-4 rounded-xl border border-bp-border bg-bp-surface-1 p-[18px]"
      >
        <div className="flex items-center gap-2.5 font-display text-xl leading-none font-bold tracking-[0.02em]">
          <ClubCrest team={DEMO.home} size={32} />
          <span>{DEMO.home.name}</span>
          <span className="font-mono text-xs font-medium text-bp-text-muted">v</span>
          <span>{DEMO.away.name}</span>
          <ClubCrest team={DEMO.away} size={32} />
          <Button type="button" variant="secondary" size="sm" className="ml-auto" onClick={play}>
            Replay
          </Button>
        </div>

        <div className="flex justify-end">
          <p className="m-0 max-w-[85%] rounded-[12px_12px_4px_12px] border border-bp-border bg-bp-surface-2 px-3.5 py-2.5 text-[15px]">
            {DEMO.query}
          </p>
        </div>

        <div className="grid grid-cols-1 gap-3.5 min-[521px]:grid-cols-[56px_minmax(0,1fr)]">
          <AgentOrb state={hasRun ? agent.state : { phase: "idle" }} size="message" />
          <div className="grid min-w-0 content-start gap-2.5">
            <div
              role="status"
              aria-live="polite"
              data-state={working ? phase : "done"}
              className={cn("min-h-[1.5em] pt-1 font-mono text-xs", working ? "text-bp-text" : "text-bp-text-muted")}
            >
              {caption}
            </div>
            <StageTicker stages={stages} />
            {answerShown && result?.baseline && result.adjusted && (
              <div className="grid gap-3">
                <ProbabilityBars
                  home={DEMO.home.name}
                  away={DEMO.away.name}
                  baseline={result.baseline}
                  adjusted={result.adjusted}
                />
                <div className="grid gap-1.5">
                  {result.adjustments.map((adjustment, index) => (
                    <AdjustmentChip key={index} adjustment={adjustment} homeName={DEMO.home.name} awayName={DEMO.away.name} />
                  ))}
                </div>
                <p className="m-0 text-sm text-bp-text-muted">{result.explanation}</p>
              </div>
            )}
          </div>
        </div>
        <span className="font-mono text-xs text-bp-text-muted">Recorded from the real engine and replayed here, so it spends no chat.</span>
      </div>
    </div>
  );
}
