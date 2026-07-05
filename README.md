# BundesPredict

**Live at [bundespredict.vercel.app](https://bundespredict.vercel.app)**

![Ask about a fixture, watch the agent work, get baseline-vs-adjusted odds with an explanation](docs/demo.gif)

A Bundesliga match predictor with two layers that stay deliberately separate:

- **A Dixon–Coles / Poisson model** (hand-written weighted MLE, time decay,
  promoted-team shrinkage, temperature-scaled calibration) produces the
  probabilities.
- **An LLM agent** reads plain-English match context — "their striker is out and
  it's going to storm" — and turns it into small, bounded, typed adjustments to
  the model's expected-goals inputs, re-runs the model, and explains what moved
  and why.

The model does the maths, the LLM does the words. There is deliberately no tool
through which the LLM can set a probability: it can only request expected-goals
adjustments, every one of which is clamped server-side (±0.6 xG) and logged, so
each answer is auditable back to the exact fitted parameters and the exact
adjustments applied.

!["Kane is out injured and it's stormy" — the odds shift, and every applied adjustment shown as an audited chip](docs/screenshot-prediction.png)

## How it fits together

```
┌──────────────┐  SSE   ┌─────────────────────────────────┐
│ Next.js chat │◄──────►│ FastAPI                         │
│  prob bars   │        │  ┌───────────────────────────┐  │
│  heatmap     │        │  │ Agent (tool-calling loop) │  │
│  adjustments │        │  └────────────┬──────────────┘  │
└──────────────┘        │      tools:   │ predict_match   │
                        │               │ predict_with_…  │
                        │               │ get_team_form   │
                        │               │ lookup_player   │
                        │  ┌────────────▼──────────────┐  │
                        │  │ Model engine (pure)       │  │
                        │  │  Dixon–Coles → score      │  │
                        │  │  matrix → every market    │  │
                        │  └────────────┬──────────────┘  │
                        └───────────────┼─────────────────┘
                                        │ reads fitted params
                        ┌───────────────▼─────────────────┐
                        │ Postgres: matches, model_runs,   │
                        │ team_params, predictions (audit) │
                        └───────────────▲─────────────────┘
                                        │
                          scripts/refit.py (offline job:
                          ingest → fit → persist params)
```

The boundaries are the point. `src/bundespredict/model/` is pure — no I/O, no
DB, no LLM; given parameters and adjustments it returns a distribution, which is
what makes it unit-testable (parameter recovery, invariants, monotonicity,
clamping). Serving never fits: the API loads the latest persisted run, and
training happens offline in `scripts/refit.py`.

One score matrix `P(home=i, away=j)` drives everything — 1X2, over/under 2.5,
both-teams-to-score, correct scores are all slices of the same distribution, so
the markets can never disagree with each other.

## How good is it, honestly?

Backtested walk-forward (refit every gameweek, each fit sees only results
strictly before that round's kickoff) over five seasons, 1,827 out-of-sample
predictions — full details in [`reports/backtest_report.md`](reports/backtest_report.md):

- **RPS 0.2045** vs **0.1967** for the de-vigged closing market consensus. The
  model is *behind* the market, which is the expected result: the closing line
  aggregates more information than any goals-only model. Landing within a
  hundredth of it means the core is sound, not that it prints money.
- **Well calibrated**: ECE ≈ 0.01; temperature scaling landed at T = 1.139,
  i.e. the raw probabilities were already close to honest.
- **CLV +0.24%** on a value-betting sim (ROI is variance-dominated noise at this
  sample size; closing-line value is the signal worth reading).
- **Market blend: an honest null.** A log-opinion-pool blend of the calibrated
  model with the de-vigged opening odds, weight chosen walk-forward, gave the
  market full weight (w = 1.0) — out-of-sample log-likelihood rises monotonically
  toward the pure open. A goals-only Dixon-Coles carries no signal the opening
  line hasn't already priced in; the blend machinery stays so that claim gets
  re-tested automatically whenever the base model improves.

The adjustment layer makes no accuracy claims at all. Contextual magnitudes
("first-choice striker out ≈ −0.35 xG") can't be backtested — there's no labeled
history of them — so they live in a knowledge base where every range carries
either a citation or an explicit `heuristic` label, and the feature is framed as
what it is: an auditable, bounded what-if with an explanation, not an edge.

## Running it

Copy the env template into a local `.env` (gitignored):

```bash
POSTGRES_USER=bundespredict
POSTGRES_PASSWORD=bundespredict
POSTGRES_DB=bundespredict
DATABASE_URL=postgresql://bundespredict:bundespredict@localhost:5433/bundespredict
ANTHROPIC_API_KEY=sk-ant-...        # the agent; endpoints 503 without it
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
# AGENT_MODEL=claude-sonnet-4-6     # optional; defaults to Haiku for cheap dev
```

Then the whole stack:

```bash
docker compose -f infra/docker-compose.yml up --build
```

- Web: http://localhost:3000 · API: http://localhost:8000/health
- Postgres publishes host port **5433** (`POSTGRES_HOST_PORT` to change)

Or without Docker (Postgres still via compose):

```bash
docker compose -f infra/docker-compose.yml up -d db
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,model,agent]"
uvicorn app.main:app --app-dir apps/api --reload   # api on :8000, from repo root
cd apps/web && npm install && npm run dev          # web on :3000
```

### Data + a fitted model

```bash
python scripts/download_seasons.py --start 2019 --end 2025   # CSVs -> data/raw/
alembic upgrade head                   # create the schema
python -m bundespredict.data.ingest    # upsert CSVs into Postgres (idempotent)
python scripts/refit.py --skip-download   # fit + persist serving parameters
python scripts/download_fixtures.py    # upcoming schedule (OpenLigaDB)
```

`refit.py` is also the recurring job: run it after a matchday and it re-pulls
the current season, re-ingests, refits on the full history and persists a new
versioned run, which serving picks up on the next request. `download_fixtures.py`
keeps the upcoming schedule mirrored (it's how "predict Dortmund's next game"
resolves the opponent); run it alongside.

The backtest + calibration report is regenerated with
`python scripts/run_backtest.py` (needs `pip install -e ".[model,report]"`).

## Checks

```bash
ruff check . && ruff format --check . && mypy && pytest
cd apps/web && npx tsc --noEmit && npm run lint
```

Tests worth calling out: parameter recovery (simulate from known parameters,
refit, assert recovery — if that passes, the MLE is almost certainly right), the
ρ=0 reduction to independent Poisson, score-matrix/market invariants, clamping
and the λ-floor, and agent-loop tests that run against recorded transcripts so
CI never touches the live API.

## Deployment

- **Web** → Vercel (project root `apps/web`; `NEXT_PUBLIC_API_BASE_URL` points
  at the API).
- **API** → Railway, built from `infra/Dockerfile.api` (`railway.json` wires the
  Dockerfile + `/health` check). Env: `DATABASE_URL`, `ANTHROPIC_API_KEY`,
  `AGENT_MODEL`, `WEB_ORIGIN` (the web URL, for CORS).
- **Postgres** → Neon. Seeded once with `alembic upgrade head` → ingest →
  `refit.py` → `download_fixtures.py`.
- **Retraining** → a GitHub Actions workflow (`.github/workflows/refit.yml`)
  refits on the latest results and refreshes the fixture schedule every Monday,
  writing a new versioned parameter run that serving picks up on the next
  request — the model never fits inside a request, in production either.
