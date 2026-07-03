# PRD — NBA Shot Quality Model & Dashboard

## Project Overview

A portfolio project that builds a shot-quality (expected field goal %) model for NBA shots using publicly available shot location data, then serves it through a live, interactive website. The site lets users explore shot charts, compare each player's actual FG% against the model's expected FG% ("shot-making skill"), and browse a league-wide leaderboard.

**Primary goal:** demonstrate applied ML/modeling skill (feature engineering under real data constraints, rigorous evaluation, calibration) combined with the ability to ship a polished, real-feeling web product — not just a notebook.

**Audience:** portfolio reviewers (recruiters, engineers, basketball-analytics-interested people) browsing casually on desktop.

**Core concept:** for every shot attempt, the model predicts the probability it goes in (`xFG%`) based on shot difficulty factors, independent of who took the shot. Comparing a player's actual FG% to their expected FG% (aggregated across their shots) isolates shot-making skill from shot selection/difficulty.

---

## Core Requirements

### Data
- Pull shot data via `nba_api` (`shotchartdetail`) for the **last 3 completed NBA seasons**.
- Include all players with a meaningful sample size across the 3-season window (~50+ total attempts), so player search covers rotation players without drowning in noise. Leaderboard applies its own stricter threshold (250+ attempts/season).
- **Chronological train/test split**: seasons 1–2 for training, most recent season held out entirely for testing. Avoids leakage from within-season streaks and mirrors real deployment (predicting unseen future shots).

### Known Data Limitations (must be handled honestly)
`nba_api`'s per-shot endpoint does **not** include true per-shot defender distance, shot clock, or a contested-shot flag — that tracking data isn't publicly exposed.

| Signal | Status | Approach |
|---|---|---|
| Shot distance, zone, angle | Real, per-shot | Used directly |
| Action type (pullup, catch-and-shoot, layup, dunk, step-back, etc.) | Real, per-shot | Primary real proxy for contest level |
| Period, time remaining, home/away, score margin | Real, per-shot | Game-situation features |
| Defender distance | Not available per-shot | League-average FG% prior joined on (shot zone, distance bucket) from aggregated tracking dashboards — labeled as an approximation on the Methodology page |
| Shot clock / contested flag | Not available at all | Not used |

### Model
- **Algorithm:** XGBoost, binary classification (make vs. miss).
- **Primary metric:** log loss (predicted probabilities are shown directly to users as "expected FG%," so calibration matters more than raw accuracy).
- **Secondary metrics:** AUC-ROC, Brier score, calibration curve.
- Model artifact, feature importances, and calibration plot must be persisted for the Methodology page.

### Serving
- Flask app must serve **only from a local SQLite database**, never call `nba_api` at request time (rate-limit risk, latency).
- SQLite is populated once via an offline batch pipeline (pull → feature engineer → train → score → write to DB). **One-time historical build** — no live/automated refresh in v1.

### Design
- Desktop-first; responsive enough not to visibly break on mobile, not optimized for it.
- Dark mode, NBA.com/ESPN-inspired aesthetic — dark background, team-colored accents, bold stat callouts.

---

## Core Features

### 1. Player Page
- Search/select a player
- Interactive hexbin shot chart for that player, color-coded by outcome/xFG%
- Actual FG% vs. expected FG% — overall and broken down by shot zone
- Season filter

### 2. Leaderboard
- Ranks players by **actual FG% − expected FG%** ("shot-making skill")
- Qualification threshold: 250+ shot attempts (season-based)
- Season selector: single season or full 3-year combined sample
- Single clean sort metric for v1 (multi-metric sorting is backlog)

### 3. Shot Explorer
- Hexbin heatmap visualization (classic NBA.com style)
- Default view: league-wide aggregate
- Player/team selector to filter down
- Filters: season, shot zone
- Hover tooltips with shot details (distance, action type, xFG%, actual result)

### 4. Methodology Page
- Model metrics (log loss, AUC, Brier score)
- Calibration plot
- Feature importance chart
- Plain-language explanation of data limitations and approximations — transparency as a credibility feature

### Out of Scope for v1 (backlog)
- Team page / team-level aggregates
- Head-to-head player comparison
- Multi-metric leaderboard sorting (by volume, by zone-specific skill, etc.)
- Automated/periodic data refresh
- Mobile-optimized experience

---

## Core Components

1. **Offline data pipeline** (Python script, run locally/manually)
   - `nba_api` puller — fetches `shotchartdetail` for scoped players/seasons, plus aggregated tracking dashboards for the defender-distance prior
   - Feature engineering module — computes shot angle, joins defender-distance prior, assembles game-situation features
   - Training module — chronological split, XGBoost training, hyperparameter selection
   - Evaluation module — log loss, AUC, Brier score, calibration curve, feature importance (matplotlib)
   - Scoring module — runs the trained model over all shots to produce `xFG%` per shot
   - DB writer — persists shots, predictions, and model metrics/artifacts to SQLite

2. **SQLite database** — single source of truth for the Flask app; read-only at runtime
   - `shots` table (per-shot features + outcome + predicted xFG%)
   - `players` / `teams` reference tables
   - `model_metrics` table (log loss, AUC, Brier score, calibration bins, feature importances)

3. **Flask backend**
   - Route handlers for Player, Leaderboard, Shot Explorer, Methodology pages
   - Query layer over SQLite (aggregations for leaderboard, filtered shot pulls for explorer)

4. **Frontend**
   - Server-rendered templates (Jinja) + Plotly.js for interactive hexbin charts and hover tooltips
   - Dark-mode NBA-inspired styling

5. **Deployment**
   - Render (free tier), SQLite file bundled with the deployed app (read-only, so ephemeral disk isn't an issue)

---

## App/User Flow

1. **Landing page** → brief intro to the project, links to Player Page, Leaderboard, Shot Explorer, Methodology.
2. **Shot Explorer (default entry point for exploration)** → user sees league-wide hexbin heatmap → optionally filters by season/shot zone → optionally selects a specific player/team to narrow the view → hovers over hexes to see shot details in a tooltip.
3. **Leaderboard** → user sees players ranked by actual − expected FG% (qualified by 250+ attempts) → can switch season scope (single season vs. 3-year) → clicks a player row to jump to their Player Page.
4. **Player Page** → user searches or arrives via leaderboard link → sees player's hexbin shot chart, actual vs. expected FG% (overall + by zone) → can change season filter.
5. **Methodology Page** → user (or reviewer) checks how the model was built and validated → sees calibration plot, feature importances, log loss/AUC/Brier score, and a plain-language writeup of data limitations/approximations.

```
Landing
  ├─→ Shot Explorer ──(select player)──→ Player Page
  ├─→ Leaderboard ────(click player)───→ Player Page
  ├─→ Player Page ─────────────────────→ (season filter, in place)
  └─→ Methodology (linked from anywhere, standalone reference)
```

---

## Tech Stack

| Layer | Choice |
|---|---|
| Data source | `nba_api` |
| Data processing | pandas |
| Model | XGBoost |
| Model evaluation viz | matplotlib (calibration plot, feature importance — generated offline) |
| Storage | SQLite |
| Backend | Flask |
| Frontend charting | Plotly.js (interactive hexbin shot charts, hover tooltips) |
| Hosting | Render (free tier) |

---

## Implementation Plan

### Phase 1 — Data Pipeline
- Build `nba_api` puller for `shotchartdetail` across 3 seasons, scoped player set
- Pull aggregated tracking dashboards for defender-distance buckets
- Persist raw pulls locally (avoid re-hitting rate-limited API during iteration)

### Phase 2 — Feature Engineering
- Compute shot angle from `LOC_X`/`LOC_Y`
- Join league-average defender-distance prior by (shot zone, distance bucket)
- Assemble game-situation features (period, time remaining, home/away, score margin)
- Build final training table with chronological season labels

### Phase 3 — Model Training & Evaluation
- Chronological split (seasons 1–2 train, season 3 test)
- Train XGBoost classifier
- Evaluate: log loss (primary), AUC, Brier score, calibration curve
- Generate feature importance chart
- Save model artifact + evaluation outputs

### Phase 4 — Scoring & Database
- Score all shots (train + test) with the trained model to produce `xFG%`
- Design and create SQLite schema (`shots`, `players`, `teams`, `model_metrics`)
- Write scored shots and model metrics to SQLite

### Phase 5 — Flask App & Pages
- Scaffold Flask app + query layer over SQLite
- Build Shot Explorer (hexbin heatmap, filters, hover tooltips)
- Build Leaderboard (ranking query, qualification threshold, season selector)
- Build Player Page (search, shot chart, actual vs. expected breakdown)
- Build Methodology page (metrics, calibration plot, feature importances, limitations writeup)

### Phase 6 — Design & Polish
- Apply dark mode, NBA/ESPN-inspired styling across all pages
- Ensure desktop layout is clean; sanity-check it doesn't break on mobile

### Phase 7 — Deployment
- Deploy to Render (free tier) with the SQLite file bundled into the app
- Final smoke test of all pages against production deployment
