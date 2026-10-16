"use client";

import { useEffect, useState, type ReactNode } from "react";

import { useIslandActivity } from "@/components/brand/IslandActivity";
import { AdjustmentChip } from "@/components/signature/AdjustmentChip";
import { AgentCaption } from "@/components/signature/AgentCaption";
import { AgentOrb } from "@/components/signature/AgentOrb";
import { ProbabilityBars } from "@/components/signature/ProbabilityBars";
import { StageTicker } from "@/components/signature/StageTicker";
import { Wordmark } from "@/components/signature/Wordmark";
import { Button } from "@/components/ui/button";
import { captionFor, useAgentState, type OrbState } from "@/lib/agent-state";
import { recordedStreams } from "@/lib/api/mocks/streams";
import { KNOWN_TOOL_NAMES, type AppliedAdjustment, type PredictResponse } from "@/lib/api/types";

import { Section } from "../Section";
import { STREAMS } from "./streams";
import { useStreamReplay } from "./useStreamReplay";

const RESULT = recordedStreams.tool_heavy.find((frame) => frame.event === "result")!.data as PredictResponse;
const BASELINE = RESULT.baseline!;
const ADJUSTED = RESULT.adjusted!;

/** The recordings never hit the cap, so one hand-written chip shows the asked-versus-capped line. */
const CAPPED_ADJUSTMENT: AppliedAdjustment = {
  factor: "player_out",
  team: "home",
  target: "home_attack",
  requested_magnitude_xg: -0.85,
  effective_magnitude_xg: -0.6,
  confidence: "high",
  rationale: "Harry Kane ruled out (knee). Bayern's top scorer and highest market value in the squad.",
};

const STATE_GALLERY: ReadonlyArray<{ label: string; state: OrbState }> = [
  { label: "Idle", state: { phase: "idle" } },
  { label: "Thinking", state: { phase: "thinking" } },
  { label: "Tool: predict_match", state: { phase: "tool", tool: "predict_match", seq: 1 } },
  { label: "Tool: get_weather", state: { phase: "tool", tool: "get_weather", seq: 1 } },
  { label: "Done", state: { phase: "done" } },
  { label: "Error", state: { phase: "error", message: "The model is unavailable right now. Your chat was not counted." } },
];

const FORCE_TOOLS = KNOWN_TOOL_NAMES;

function Panel({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <div className={`grid content-start gap-3 rounded-lg border border-bp-border bg-bp-surface-1 p-4 ${className ?? ""}`}>
      <h3 className="font-mono text-xs tracking-wider text-bp-text-muted uppercase">{title}</h3>
      {children}
    </div>
  );
}

export function SignatureDemo() {
  const agent = useAgentState();
  const { play, cancel } = useStreamReplay(agent.dispatch);
  const { setAgentCaption } = useIslandActivity();
  const [forced, setForced] = useState<OrbState | null>(null);
  const [replay, setReplay] = useState<keyof typeof STREAMS | null>(null);
  const [wordmarkActive, setWordmarkActive] = useState(false);

  const state = forced ?? agent.state;
  const caption = captionFor(state);
  const working = state.phase === "thinking" || state.phase === "tool";
  const answered = agent.state.phase === "done" || (agent.state.phase === "idle" && agent.stages.length > 0 && replay !== null);

  useEffect(() => {
    setAgentCaption(working ? caption : null);
    return () => setAgentCaption(null);
  }, [working, caption, setAgentCaption]);

  const start = (name: keyof typeof STREAMS) => {
    setForced(null);
    setReplay(name);
    play(STREAMS[name].events);
  };

  const force = (next: OrbState) => {
    cancel();
    setReplay(null);
    setForced(next);
  };

  return (
    <>
      <Section id="wordmark" title="Wordmark" note="Real text with a canvas of code rain laid over Predict. The rain speeds up while the agent works.">
        <div data-testid="hero-wordmark" className="relative grid place-items-start overflow-hidden rounded-lg border border-bp-border bg-bp-bg px-4 py-10 sm:px-14 sm:py-16">
          <Wordmark size="hero" active={wordmarkActive || working} />
        </div>
        <div className="flex flex-wrap items-center gap-6 rounded-lg border border-bp-border bg-bp-surface-1 px-4 py-3">
          <div data-testid="nav-wordmark">
            <Wordmark size="nav" active={wordmarkActive || working} />
          </div>
          <span className="text-sm text-bp-text-muted">Matchday · Chat · Track record</span>
        </div>
        <label className="flex w-fit items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="size-4 accent-bp-red"
            checked={wordmarkActive}
            onChange={(event) => setWordmarkActive(event.target.checked)}
          />
          Force the active state
        </label>
      </Section>

      <Section id="orb" title="Agent orb" note="Replay a stream or force a state. Each tool call sends one bright band down the sphere.">
        <div className="flex flex-wrap gap-2">
          <Button data-testid="replay-tool-heavy" className="h-auto min-h-8 max-w-full whitespace-normal text-left" onClick={() => start("toolHeavy")}>
            Play: {STREAMS.toolHeavy.label}
          </Button>
          <Button data-testid="replay-error" variant="secondary" className="h-auto min-h-8 max-w-full whitespace-normal text-left" onClick={() => start("withError")}>
            Play: {STREAMS.withError.label}
          </Button>
        </div>
        <div className="flex flex-wrap gap-2" aria-label="Force a state">
          <Button size="sm" variant="outline" onClick={() => force({ phase: "idle" })}>
            Idle
          </Button>
          <Button size="sm" variant="outline" onClick={() => force({ phase: "thinking" })}>
            Thinking
          </Button>
          {FORCE_TOOLS.map((tool) => (
            <Button key={tool} size="sm" variant="outline" onClick={() => force({ phase: "tool", tool, seq: Date.now() })}>
              {tool}
            </Button>
          ))}
          <Button size="sm" variant="outline" onClick={() => force({ phase: "done" })}>
            Done
          </Button>
          <Button size="sm" variant="outline" onClick={() => force({ phase: "error", message: "Something went wrong. Try again." })}>
            Error
          </Button>
        </div>

        <div className="grid gap-4 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <Panel title="Stage · 280px" className="place-items-center py-6">
            <div data-testid="stage-orb">
              <AgentOrb state={state} size="stage" />
            </div>
            <AgentCaption state={state} className="text-center" />
          </Panel>
          <div className="grid content-start gap-4">
            <Panel title="Chat header · 24px">
              <div className="flex items-center gap-2.5 rounded-lg border border-bp-border bg-bp-bg px-3 py-2.5">
                <AgentOrb state={state} size="chatHeader" />
                <span className="font-display text-xl font-bold tracking-wide">FCB v BVB</span>
                <span className="ml-auto font-mono text-xs text-bp-text-muted">Sat 18:30</span>
              </div>
            </Panel>
            <Panel title="Streaming message · 56px">
              <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-3 rounded-lg border border-bp-border bg-bp-bg p-3">
                <AgentOrb state={state} size="message" />
                <div className="grid min-w-0 content-start gap-2">
                  <AgentCaption state={state} />
                  <StageTicker stages={agent.stages} collapsed={answered} />
                </div>
              </div>
            </Panel>
          </div>
        </div>

        <Panel title="Every state, 120px">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            {STATE_GALLERY.map(({ label, state: galleryState }) => (
              <figure key={label} data-testid={`gallery-${galleryState.phase}${galleryState.phase === "tool" ? `-${galleryState.tool}` : ""}`} className="grid justify-items-center gap-2">
                <AgentOrb state={galleryState} size={120} />
                <figcaption className="text-center font-mono text-xs text-bp-text-muted">{label}</figcaption>
              </figure>
            ))}
          </div>
        </Panel>
      </Section>

      <Section id="bars" title="Probability bars" note="The adjusted bar tweens from the baseline over 400ms. Arrows stay neutral so green and red only mean win and lose.">
        <div className="grid gap-4 md:grid-cols-2">
          <Panel title="Without news">
            <ProbabilityBars home="Bayern" away="Mainz" baseline={BASELINE} />
          </Panel>
          <Panel title="With your news">
            <ProbabilityBars home="Bayern" away="Mainz" baseline={BASELINE} adjusted={ADJUSTED} />
          </Panel>
          <Panel title="Draw leads, three decimals">
            <ProbabilityBars
              home="Schalke"
              away="Mainz"
              baseline={{ p_home: 0.3349, p_draw: 0.3352, p_away: 0.3299, exp_home_goals: 1.18, exp_away_goals: 1.16 }}
            />
          </Panel>
          <Panel title="Long shot under 1%">
            <ProbabilityBars
              home="Bayern"
              away="Paderborn"
              baseline={{ p_home: 0.968, p_draw: 0.028, p_away: 0.004, exp_home_goals: 3.1, exp_away_goals: 0.4 }}
            />
          </Panel>
        </div>
      </Section>

      <Section id="chips" title="Adjustment chips" note="Hover or focus a chip to read the agent's rationale. The last one asks for more than the cap allows.">
        <div className="flex flex-wrap gap-2">
          {[...RESULT.adjustments, CAPPED_ADJUSTMENT].map((adjustment) => (
            <AdjustmentChip key={adjustment.rationale} adjustment={adjustment} homeName="Bayern" awayName="Mainz" />
          ))}
        </div>
      </Section>

      <Section id="ticker" title="Stage ticker" note="Fills as the replay runs and folds once the answer arrives.">
        <Panel title="Live from the replay">
          <StageTicker stages={agent.stages} collapsed={answered} />
          {agent.stages.length === 0 && <p className="text-sm text-bp-text-muted">Play a stream above to fill the list.</p>}
        </Panel>
      </Section>
    </>
  );
}
