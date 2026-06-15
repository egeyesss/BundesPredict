# BundesPredict

A side project for predicting Bundesliga match results. The idea: a statistical
model (Dixon–Coles / Poisson) does the actual probabilities, and on top of that an
LLM reads plain-English match context ("striker's injured, pouring rain, nothing to
play for") and turns it into small, bounded tweaks to the model's inputs, then
explains what changed. The model does the maths, the LLM does the words.

Early days — most of this is still just scaffolding. Notes below are mostly for me.

## Layout

```
apps/api/         FastAPI backend
apps/web/         Next.js frontend
src/bundespredict/
  model/          the prediction maths
  data/           ingestion + team-name mapping
  agent/          LLM tools, prompt, the adjustments stuff
  eval/           backtesting + metrics
scripts/          download_seasons.py
infra/            Dockerfiles + docker-compose
tests/
notebooks/        for messing around / EDA
```

## Running it

Easiest is Docker (brings up the db, api and web together):

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up --build
```

- API health check: http://localhost:8000/health
- Frontend: http://localhost:3000
- Postgres on host port **5433** (5432 was taken by my local one)

Without Docker:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload      # api on :8000, run from repo root

cd apps/web && npm install && npm run dev   # web on :3000
```

## Getting data

Season CSVs (results + bookmaker odds + match stats) from football-data.co.uk:

```bash
python scripts/download_seasons.py --start 2019 --end 2025
# files land in data/raw/ (gitignored)
```

Then create the schema and load the CSVs into Postgres (idempotent — safe to
re-run, it upserts rather than duplicating):

```bash
alembic upgrade head                  # create the tables
python -m bundespredict.data.ingest   # parse data/raw/*.csv -> Postgres
```

Both read `DATABASE_URL` (defaults to the local compose DB on :5433). Team names
get normalized to canonical (Transfermarkt-style) names via the alias map in
`src/bundespredict/data/team_aliases.py`; an unknown club fails loudly at ingest
instead of silently creating a duplicate.

Poke around the data in `notebooks/eda.ipynb` (needs the `eda` extra:
`pip install -e ".[eda]"`).

## Checks before pushing

```bash
ruff check . && ruff format --check . && mypy && pytest
cd apps/web && npx tsc --noEmit && npm run lint
```

## TODO (roughly, for me)

- [x] ingest the season CSVs into Postgres, sort out team-name mapping
- [ ] fit the Poisson / Dixon–Coles model, turn it into match probabilities
- [ ] calibration + backtest against bookmaker odds
- [ ] the LLM adjustment layer + chat UI
