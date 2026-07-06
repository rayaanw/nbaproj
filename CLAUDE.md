# CLAUDE.md — Agent README

This file is the entry point for any AI agent working on this codebase.
Read it fully before making changes.

---

## Project Summary

NBA Shot Quality Model & Dashboard is a portfolio project that predicts the probability any given NBA shot goes in (expected FG%, `xFG%`) using shot location and situational data, then serves the results through a live, interactive website.

Core loop:
1. An offline pipeline pulls the last 3 NBA seasons of shot data via `nba_api`
2. Features (shot distance, zone, angle, action type, game situation, defender-distance prior) are engineered and used to train an XGBoost classifier
3. The model is evaluated chronologically (train on seasons 1-2, test on season 3) and scored across all shots
4. Scored shots, leaderboard aggregates, and model evaluation artifacts are written to a local SQLite database
5. A Flask app serves three core pages — Player Page, Leaderboard, Shot Explorer — plus a Methodology page, reading only from that SQLite database (never calling `nba_api` at request time)

This is a **one-time historical build** — the dataset and model are not live-updating. There is no user auth, no write access from the app, and no ongoing data refresh in v1.

---

## Repository Structure

```
/
  pipeline/     Offline data pull, feature engineering, training, scoring scripts (run locally, in order)
  app/          Flask web application (routes, templates, static assets, query layer)
  data/
    raw/        Raw nba_api pulls (shots, play-by-play, defender-distance priors) — gitignored
    processed/  Cleaned/joined feature tables — gitignored
  models/       Trained model artifact, evaluation metrics, calibration/feature-importance plots — gitignored except MODEL_CARD.md
  db/           schema.sql and the SQLite database file consumed by the Flask app
  PRD-NBAShotQualityModel.md   Full product requirements document
  todo.md       Step-by-step implementation plan (T-001–T-049) with dependency graph
  CLAUDE.md     This file
```

---

## Tech Stack

| Layer | Choice |
|---|---|
| Data source | `nba_api` (wraps stats.nba.com) |
| Data processing | pandas |
| Model | XGBoost (binary classifier, make/miss) |
| Model evaluation viz | matplotlib (calibration plot, feature importance — generated offline) |
| Storage | SQLite (read-only at app runtime) |
| Backend | Flask + gunicorn (production) |
| Frontend charting | Plotly.js (interactive hexbin shot charts, hover tooltips) |
| Hosting | Render (free tier) |

---

## Prerequisites

- Python 3.10+
- A virtual environment tool (`venv` or `poetry`)
- macOS only: `brew install libomp` — XGBoost's compiled extension links against OpenMP at runtime and fails to import without it (`libxgboost.dylib` load error)
- No external accounts/API keys required — `nba_api` calls stats.nba.com directly with no auth, but is rate-limited (see `pipeline/config.py` for delay/retry settings)
- Network access to `stats.nba.com` for the pipeline pull steps (T-004–T-008) — some sandboxed/CI environments block this host; run the pipeline from a machine with normal internet access

---

## Install

```bash
# From the project root
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy and fill in environment variables (app config only — no secrets required):

```bash
cp app/.env.example app/.env
```

---

## Run

**1. Run the offline pipeline first** (pulls data, trains the model, populates the SQLite DB). This must be run before the app will have anything to serve — see `pipeline/README.md` and `todo.md` Phases 1-4 for the full breakdown.

```bash
python pipeline/run_all.py
```

This is slow (rate-limited `nba_api` calls across 3 seasons) and only needs to be run once, or re-run manually if you want to rebuild the dataset/model from scratch. Individual pipeline scripts are numbered (`01_pull_player_reference.py`, `02_pull_shot_charts.py`, ... `13_build_leaderboard_table.py`) and are safely resumable — already-pulled files are skipped on rerun.

**2. Run the Flask app** (reads only from `db/`, never calls `nba_api`):

```bash
python app/run.py           # dev server, http://localhost:5000
```

---

## Test

There is no automated test suite in v1. Validation instead relies on:
- `pipeline/05_validate_raw_data.py` — schema/null-rate checks on raw pulls
- `pipeline/run_all.py` sanity queries — row-count and schema checks against the finished SQLite DB (see `todo.md` T-028)
- Manual QA pass across all pages/browsers before deploy (see `todo.md` T-046, T-049)

If you add automated tests, prefer `pytest` for pipeline unit tests (feature engineering functions, query layer functions) and document the run command here.

---

## Deploy

**Web app (Render):**
```bash
# Push to the connected GitHub repo — Render auto-deploys on push to main
# The SQLite DB file (built by the offline pipeline) must be committed/bundled
# with the app, since Render's free-tier disk is ephemeral and the app is read-only at runtime.
```

There is no separate deploy step for the pipeline/model — it is run locally, and only its output (`db/*.sqlite3`) ships to production.

---

## Key Documentation

| File | Purpose |
|---|---|
| `PRD-NBAShotQualityModel.md` | Full product requirements: overview, core requirements, features, components, app flow, tech stack |
| `todo.md` | Step-by-step implementation plan — 49 tasks (T-001–T-049) across 9 phases, with subtasks and a dependency graph |
| `pipeline/README.md` | Exact pipeline run order and any manual steps (written as part of T-028.3) |
| `db/schema.sql` | SQLite schema — canonical definition of `shots`, `players`, `leaderboard`, `model_metrics`, `calibration_bins`, `feature_importance` tables |
| `models/MODEL_CARD.md` | Training date, seasons used, feature list, headline metrics for the current model artifact |

---

## Key Architectural Decisions

- **The app is read-only at runtime.** Flask only ever queries `db/*.sqlite3` via `app/queries.py`. It never calls `nba_api` directly — all data pulling, feature engineering, training, and scoring happens offline in `pipeline/`, run manually.
- **Chronological train/test split, not random.** Train on the two oldest seasons, test on the most recent, to avoid leakage from within-season player streaks and to mirror real deployment (predicting unseen future shots). Do not change this to a random split without updating `PRD-NBAShotQualityModel.md`.
- **Data limitations are handled honestly, not hidden.** `nba_api`'s public endpoints do not expose true per-shot defender distance, shot clock, or a contested-shot flag. `ACTION_TYPE` is used as the primary real per-shot contest proxy; a league-average defender-distance prior (joined by shot zone + distance bucket) is used as a clearly-labeled supplementary approximation. This distinction is surfaced on the Methodology page — do not present the defender-distance prior as true per-shot tracking data anywhere in the UI.
- **Score margin requires a play-by-play join.** `shotchartdetail` does not include live score — `score_margin` is derived by joining play-by-play data (`pipeline/03_pull_playbyplay.py`) on `GAME_ID` + clock time. See `todo.md` T-006/T-011.
- **One-time historical build.** There is no scheduled/automated data refresh in v1. If you add one, update the "Run" and "Deploy" sections above and the PRD's deployment section.
- **Leaderboard uses a pre-aggregated table**, not on-the-fly aggregation, for performance (`pipeline/13_build_leaderboard_table.py` → `leaderboard` table). Qualification threshold (`LEADERBOARD_MIN_ATTEMPTS`) is defined in `pipeline/config.py`, not hardcoded in query/route code.

---

## Environment Variables Reference

### app/.env
```
DB_PATH=
DEBUG=
```

No API keys or secrets are required anywhere in this project — `nba_api` requires no authentication.
