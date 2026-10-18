"use client";

import { RotateCcw } from "lucide-react";

import { AgentCaption } from "@/components/signature/AgentCaption";
import { AgentOrb } from "@/components/signature/AgentOrb";
import { useReducedMotion } from "@/components/signature/reduced-motion";
import { StageTicker } from "@/components/signature/StageTicker";
import { Button } from "@/components/ui/button";
import type { Team } from "@/lib/api/types";
import type { AssistantTurn as Turn } from "@/lib/chat/transcript";

import "./chat.css";
import { Explanation, closeOpenEmphasis } from "./Explanation";
import { ResultCard } from "./ResultCard";
import { useTypewriter } from "./use-typewriter";

const CHARS_PER_SECOND = 90;

type AssistantTurnProps = {
  turn: Turn;
  teams: readonly Team[] | undefined;
  onWritten: () => void;
  onRetry: (text: string) => void;
};

/** One answer: the orb and its caption, the agent's steps, the explanation as it types, then the numbers. */
export function AssistantTurn({ turn, teams, onWritten, onRetry }: AssistantTurnProps) {
  const reducedMotion = useReducedMotion(false);
  const { visible, typing } = useTypewriter(turn.text, {
    enabled: turn.animate && turn.phase === "writing" && !reducedMotion,
    charsPerSecond: CHARS_PER_SECOND,
    onDone: turn.phase === "writing" ? onWritten : undefined,
  });

  const failed = turn.phase === "failed" || turn.phase === "cut_off";
  const showExplanation = turn.text !== "" && turn.phase !== "working";

  return (
    <div className="mx-auto grid w-full max-w-[760px] grid-cols-[56px_minmax(0,1fr)] gap-x-3.5 gap-y-3 max-[520px]:grid-cols-[36px_minmax(0,1fr)] max-[520px]:gap-x-2.5">
      <div>
        <AgentOrb state={turn.agent.orb} size="message" className="max-[520px]:size-9!" />
      </div>

      <div className="grid min-w-0 content-start gap-3">
        {!(failed && turn.error !== null) && <AgentCaption state={turn.agent.orb} className="pt-1" />}
        {failed && turn.error !== null && (
          <p role="status" className="pt-1 font-mono text-xs text-bp-red-text">
            {turn.error}
          </p>
        )}

        <StageTicker stages={turn.agent.stages} collapsed={turn.phase !== "working"} />

        {showExplanation &&
          (typing ? (
            <div>
              <div className="sr-only">
                <Explanation text={turn.text} />
              </div>
              <div aria-hidden="true" className="caret">
                <Explanation text={closeOpenEmphasis(visible)} />
              </div>
            </div>
          ) : (
            <Explanation text={turn.text} />
          ))}

        {failed && turn.retryText !== null && (
          <div>
            <Button type="button" variant="secondary" size="sm" onClick={() => onRetry(turn.retryText ?? "")}>
              <RotateCcw /> {turn.phase === "cut_off" ? "Ask again" : "Try again"}
            </Button>
          </div>
        )}
      </div>

      {turn.phase === "done" && turn.result && (
        <div className="col-start-2 min-w-0 max-[520px]:col-span-full max-[520px]:col-start-1">
          <ResultCard result={turn.result} teams={teams} />
        </div>
      )}
    </div>
  );
}
