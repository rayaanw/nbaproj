# Implementation Plan — NBA Shot Quality Model & Dashboard

**Format:** Each task has a unique ID (`T-###`), a dependency list, context, and subtasks.
**Rule:** No task should be started until all its dependencies are marked complete. Tasks build strictly on top of one another — there are no standalone/orphan tasks.

---

## Phase 0 — Project Setup & Environment

---

### T-001 · Initialize Project Repository & Structure

**Depends on:** none
**Context:** Establishes the base folder layout separating the offline data/ML pipeline from the Flask web app, so the two concerns (modeling vs. serving) never get tangled. This is the foundation every later task writes into.

- [x] **T-001.1** Create root project folder `nba-shot-quality-model/` with subfolders: `pipeline/` (data pull, feature engineering, training, scoring scripts), `app/` (Flask application), `data/raw/`, `data/processed/`, `models/` (trained artifacts, plots), `db/` (SQLite file lives here)
- [x] **T-001.2** Initialize a git repository at the project root; create `.gitignore` covering `venv/`, `__pycache__/`, `data/raw/*`, `data/processed/*`, `*.sqlite3`, `.env` — repo/initial commit already existed from planning; `.gitignore` added now
- [x] **T-001.3** Add a placeholder `.gitkeep` in each empty data/model folder so the structure is preserved in git
- [x] **T-001.4** Write a minimal `README.md` stub with project name and one-line description (full docs added later)
- [x] **T-001.5** Make an initial commit — committed as "Scaffold project structure (pipeline/, app/, data/, models/, db/)"

---

### T-002 · Install & Configure Core Dependencies

**Depends on:** T-001
**Context:** Pins the exact tech stack (nba_api, pandas, xgboost, matplotlib, flask, plotly) so the environment is reproducible and versions don't drift mid-project.

- [x] **T-002.1** Create a Python virtual environment (`venv` or `poetry`) at project root
- [x] **T-002.2** Install core pipeline packages: `nba_api`, `pandas`, `xgboost`, `scikit-learn` (metrics/calibration utilities), `matplotlib` — also added `pyarrow` (required for `.parquet` I/O used throughout the pipeline, not listed explicitly in the PRD but needed by every read/write step)
- [x] **T-002.3** Install app packages: `flask`, `python-dotenv` — also added `gunicorn` now since T-047 needs it later and it's zero-cost to pin today
- [x] **T-002.4** Freeze installed versions into `requirements.txt`
- [x] **T-002.5** Write a smoke-test script `pipeline/00_smoke_test.py` that imports every installed package and prints versions; run it to confirm the environment is healthy — passes. **Real environment gap found and fixed:** XGBoost's compiled extension failed to load on macOS (`libxgboost.dylib` needs OpenMP) until `brew install libomp` was run; documented as a prerequisite in `CLAUDE.md`.

---

### T-003 · Define Project Configuration & Constants

**Depends on:** T-002
**Context:** Centralizes the decisions already locked in the PRD (season scope, thresholds, file paths) into one config module so no script hardcodes magic values that later need to change in five places.

- [x] **T-003.1** Create `pipeline/config.py` defining the 3 target season strings (e.g. `"2022-23"`, `"2023-24"`, `"2024-25"`), with the most recent marked as the `TEST_SEASON` and the other two as `TRAIN_SEASONS`
- [x] **T-003.2** Add constants: `MIN_PLAYER_ATTEMPTS = 50` (inclusion threshold for player dataset) and `LEADERBOARD_MIN_ATTEMPTS = 250` (leaderboard qualification threshold)
- [x] **T-003.3** Add file path constants for `data/raw/`, `data/processed/`, `models/`, and the SQLite DB path in `db/`
- [x] **T-003.4** Add a `REQUEST_DELAY_SECONDS` constant (e.g. 0.6–1s) and `MAX_RETRIES` constant for polite, resilient `nba_api` polling (stats.nba.com rate-limits aggressively)

---

## Phase 1 — Data Ingestion

---

### T-004 · Build Player & Season Reference Puller

**Depends on:** T-003
**Context:** Before pulling shot-by-shot data, we need to know which players qualify (≥`MIN_PLAYER_ATTEMPTS` across the 3-season window) and which team they played for each season, so later pulls are scoped and don't waste calls on players with negligible data.

- [x] **T-004.1** Write `pipeline/01_pull_player_reference.py` using an `nba_api` league-wide player stats endpoint to fetch all players who played in each of the 3 target seasons — uses `leaguedashplayerstats`
- [x] **T-004.2** Aggregate total field goal attempts per player across the 3-season window
- [x] **T-004.3** Filter to players meeting `MIN_PLAYER_ATTEMPTS`; keep player ID, name, and team ID(s) per season (players can change teams)
- [x] **T-004.4** Save the result to `data/raw/players_reference.parquet`
- [x] **T-004.5** Log summary counts (players in, players after filter) to confirm the scope is reasonable before the expensive per-player pull begins
- **Verification note:** stats.nba.com is unreachable from this build sandbox (network blocked), so this could not be run against live data. Logic was verified by monkey-patching `LeagueDashPlayerStats` with a synthetic response matching real columns (`PLAYER_ID`, `PLAYER_NAME`, `TEAM_ID`, `TEAM_ABBREVIATION`, `FGA`) and confirming the attempt-aggregation/filter/save steps behave correctly (a below-threshold player was correctly excluded). Run for real on a machine with network access before trusting the output.

---

### T-005 · Build Shot Chart Data Puller

**Depends on:** T-004
**Context:** This is the core dataset — per-shot location, distance, zone, and action type for every qualifying player across 3 seasons, via `shotchartdetail`. It's the slowest, most rate-limit-sensitive part of the pipeline, so it must be resumable and cache-friendly.

- [x] **T-005.1** Write `pipeline/02_pull_shot_charts.py` that loops over each (player, season) pair from `players_reference.parquet` and calls the `shotchartdetail` endpoint
- [x] **T-005.2** Add retry-with-backoff logic and a fixed delay between calls (using `REQUEST_DELAY_SECONDS`/`MAX_RETRIES` from config) to avoid IP throttling — shared `call_with_retry()` helper in `pipeline/utils.py`, used by all pullers
- [x] **T-005.3** After each successful pull, write the raw response to `data/raw/shots/{season}/{player_id}.parquet` — one file per player/season so a crashed run can resume without re-pulling completed players
- [x] **T-005.4** At the start of the loop, skip any (player, season) pair whose output file already exists, so the script is safely re-runnable — verified via a mocked rerun that correctly reported `skipped(existing)` instead of re-pulling
- [x] **T-005.5** Log failures (player/season pairs that errored after max retries) to `data/raw/shots/_failures.log` for manual follow-up
- [ ] **T-005.6** Run the full pull for all 3 seasons and confirm file counts match the expected player/season pair count — **not run**; requires network access to `stats.nba.com`, which this sandbox cannot reach. Logic verified with mocked responses only (see T-004 verification note). Run this for real per the workflow documented in `CLAUDE.md`/`pipeline/README.md` (T-028.3).

---

### T-006 · Build Play-by-Play Puller for Score Margin

**Depends on:** T-004
**Context:** `shotchartdetail` does not include the live score at the time of each shot, which we need for the score-margin (game situation) feature. This requires a separate pull of play-by-play data per game, matched later to shots by `GAME_ID` and event number.

- [x] **T-006.1** From the shot chart scope, derive the distinct set of `GAME_ID`s that will need to be covered (can run in parallel with T-005 once player/season scope is known, or after — either is fine since it depends only on T-004) — implemented as reading distinct `GAME_ID`s directly out of whatever shot-chart parquet files already exist under `data/raw/shots/`, rather than a separate lookup call; safe to run partway through T-005 and rerun later to pick up new games
- [x] **T-006.2** Write `pipeline/03_pull_playbyplay.py` that pulls play-by-play data per unique `GAME_ID` (score fields included), with the same retry/backoff/delay approach as T-005 — uses `playbyplayv2`, whose `SCOREMARGIN`/`SCORE` columns give the score state directly per event (no manual score-progression math needed for T-011)
- [x] **T-006.3** Save one file per game to `data/raw/playbyplay/{game_id}.parquet`, skipping already-pulled games on re-run — resumability verified via mocked rerun
- [x] **T-006.4** Log failures the same way as T-005.5
- **Verification note:** same sandbox network constraint as T-004/T-005 — logic verified with a mocked `PlayByPlayV2` response, not a live pull.

---

### T-007 · Build Defender-Distance Aggregate Puller

**Depends on:** T-003
**Context:** True per-shot defender distance isn't available, so we pull the league's aggregated shot-distance × defender-distance FG% tables (tracking dashboard endpoints) per season, to use later as a supplementary league-average prior. This doesn't depend on the player list — it's a league-wide aggregate — so it only needs the season scope from config.

- [x] **T-007.1** Write `pipeline/04_pull_defender_distance_priors.py` calling the relevant `nba_api` tracking dashboard endpoint(s) for each of the 3 seasons — uses `leaguedashplayerptshot` called once per (shot-distance bucket × closest-defender-distance bucket) combination, league-wide (no player/team filter), summing `FGM`/`FGA` across all returned player rows to get a single league-wide cell
- [ ] **T-007.2** Confirm the returned data can be organized into buckets of (shot distance range, closest defender distance range) with associated FG% — **partially done.** The bucketing logic itself is verified (mocked response → correct 7×4=28-row table per season, see `SHOT_DIST_RANGES`/`CLOSE_DEF_DIST_RANGES` in the script). **Not yet confirmed:** whether the specific filter string values (e.g. `"Less Than 5 ft."`, `"0-2 Feet - Very Tight"`) are exactly what the live `stats.nba.com` API expects — these are documented/best-known values but couldn't be checked against a live call from this sandbox. The script raises loudly on any empty bucket result specifically so this gets caught immediately on the first real run rather than silently producing a broken prior table.
- [x] **T-007.3** Save one table per season to `data/raw/defender_priors/{season}.parquet`

---

### T-008 · Raw Data Validation & Caching Layer

**Depends on:** T-005, T-006, T-007
**Context:** Before spending time on feature engineering, verify the raw pulls are complete and sane. Catching a bad pull here is far cheaper than discovering it after training a model on corrupted data.

- [x] **T-008.1** Write `pipeline/05_validate_raw_data.py` that checks: expected file counts (per T-005/T-006 scope) are present, no file has zero rows unexpectedly, and column schemas are consistent across all shot-chart files
- [x] **T-008.2** Check null rates on key columns (`LOC_X`, `LOC_Y`, `SHOT_DISTANCE`, `ACTION_TYPE`, `SHOT_MADE_FLAG`) and fail loudly if any exceed a small threshold (e.g. >1%)
- [x] **T-008.3** Write a data manifest (`data/raw/manifest.json`) summarizing row counts per season/table, used as a sanity checkpoint for future pipeline reruns
- **Verification note:** ran end-to-end against synthetic data shaped like the T-004–T-007 outputs (6 shot files, 1 play-by-play file, 3 defender-prior files) — schema/null-rate checks and manifest generation all work correctly. Test data was deleted afterward (not committed) so it won't block the user's real pull via the resumability/skip-existing logic.

---

## Phase 2 — Feature Engineering

---

### T-009 · Merge & Consolidate Raw Shot Data

**Depends on:** T-008
**Context:** Combines the per-player/per-season shot files into one working dataset, standardizing types so every downstream feature step operates on a single clean table instead of hundreds of small files.

- [x] **T-009.1** Write `pipeline/06_consolidate_shots.py` that loads and concatenates all files under `data/raw/shots/`
- [x] **T-009.2** Standardize column names/types (e.g. ensure `SHOT_MADE_FLAG` is int 0/1, `GAME_ID` is a consistent string format for later joins) — also attaches the `SEASON` column here (from the folder name), since this is the one place the season is naturally known without an extra lookup; carried through every downstream join
- [x] **T-009.3** Drop exact duplicate rows (can occur if a script reran partially)
- [x] **T-009.4** Save the consolidated table to `data/processed/shots_consolidated.parquet`
- **Numbering note:** T-010–T-014 don't have prescribed script filenames in this plan (only T-009's `06_consolidate_shots.py` and T-015's `07_train_test_split.py` are named explicitly), so they were implemented as `06a`–`06e` to sit clearly between the two fixed scripts while still sorting in run order. See `pipeline/README.md` (T-028.3) for the full run order.
- **Verification note (applies to all of T-009–T-015):** stats.nba.com is unreachable from this build sandbox, so these scripts were verified end-to-end against realistic synthetic raw data (schema-matched fake shots/play-by-play/defender-prior files) rather than a live pull. The full chain (06 → 06a → 06b → 06c → 06d → 06e → 07) was run together and inspected at each step. **One real bug was caught this way:** the T-014 join (06e) fanned out rows 9x before a fix, because it joined only on `GAME_ID`+`GAME_EVENT_ID`; adding `SEASON` to the join key closed the gap defensively. Test data was deleted afterward so it won't interfere with the user's real pipeline run.

---

### T-010 · Compute Derived Geometric Features

**Depends on:** T-009
**Context:** Shot angle isn't provided directly — it's derived from court coordinates. This is also where we filter out nonsensical outlier shots (e.g. full-court heaves) that would otherwise add noise the model can't meaningfully learn from.

- [x] **T-010.1** Compute `shot_angle` from `LOC_X`/`LOC_Y` using `atan2`, normalized to a consistent range (e.g. degrees from the basket, 0° = straight on) — `pipeline/06a_geo_features.py` + `pipeline/features.py::compute_shot_angle_degrees`; takes the absolute value since the court is left/right symmetric for shot difficulty
- [x] **T-010.2** Bucket `SHOT_DISTANCE` into discrete ranges (e.g. 0-3ft, 3-10ft, 10-16ft, 16-3PT, 3PT, deep 3PT) for later joins with the defender-distance prior table — **deviation:** used the exact same 7 buckets as the pulled defender-distance prior (`"Less Than 5 ft."`, `"5-9 ft."`, ..., `">= 30 ft."` — see T-007.1) instead of the PRD's example zone-based buckets, so the T-013 join lines up without any relabeling
- [x] **T-010.3** Flag and exclude shots beyond a reasonable max distance (e.g. >40ft, near-halfcourt heaves) as a separate `is_heave` filter, excluded from training — flagged here, actually excluded during T-014 assembly (kept in the intermediate file for inspection)
- [x] **T-010.4** Save the enriched table (overwriting/extending `shots_consolidated.parquet` or a new `shots_geo.parquet`) — saved as `shots_geo.parquet`

---

### T-011 · Join Score Margin from Play-by-Play

**Depends on:** T-009, T-006
**Context:** Matches each shot to the live score at the moment it was taken, using the play-by-play data pulled in T-006, joined on `GAME_ID` and the closest preceding event/clock time.

- [x] **T-011.1** Load consolidated play-by-play data from `data/raw/playbyplay/`
- [x] **T-011.2** For each shot, join on `GAME_ID` + period + game clock to find the score state immediately prior to that shot event — **deviation:** joined on the exact `GAME_ID` + `GAME_EVENT_ID`/`EVENTNUM` match instead of a fuzzy clock-time join. `shotchartdetail`'s `GAME_EVENT_ID` and `playbyplayv2`'s `EVENTNUM` refer to the same underlying per-game event log, so an exact-ID `merge_asof` (backward, strictly-before) is both simpler and more precise than matching on period+clock string
- [x] **T-011.3** Compute `score_margin` (shooting team's score minus opponent's score at that moment) — uses `playbyplayv2`'s own `SCOREMARGIN` field (forward-filled per game) rather than recomputing from raw score progression, since it's already provided per event
- [x] **T-011.4** Handle unmatched shots gracefully (log count of shots that couldn't be matched to a score state; drop or impute with a documented fallback, e.g. 0) — imputes 0, logs count/percentage
- [x] **T-011.5** Save the score-margin-enriched join as `data/processed/shots_with_score_margin.parquet`
- **Verification note:** the `merge_asof`(backward, strictly-before) join logic was unit-tested directly with a small synthetic play-by-play sequence to confirm it picks up the state from the *prior* event, not the shot's own event (see todo.md's T-009 verification note for the broader sandbox network constraint).

---

### T-012 · Engineer Game-Situation & Context Features

**Depends on:** T-009
**Context:** Builds the remaining straightforward per-shot context features that don't require any external join — period, time remaining, and home/away.

- [x] **T-012.1** Compute `time_remaining_in_period` (seconds) from `MINUTES_REMAINING`/`SECONDS_REMAINING`
- [x] **T-012.2** Derive `home_away` per shot by comparing the shooting player's team ID to the game's home/visitor team fields — team ID → abbreviation lookup via `nba_api.stats.static.teams` (bundled static data, no network call needed), compared against `HTM`
- [x] **T-012.3** Encode `PERIOD` as a clean integer, handling overtime periods (5+) consistently — adds an `is_overtime` boolean flag for periods 5+
- [x] **T-012.4** Save as `data/processed/shots_context.parquet`

---

### T-013 · Join Defender-Distance Prior

**Depends on:** T-010, T-007
**Context:** Attaches the league-average FG% prior (from the aggregated tracking dashboards) to each shot, joined on season + shot-distance bucket, as the supplementary defender-proximity approximation discussed in the PRD.

- [x] **T-013.1** Load the per-season defender-distance prior tables from `data/raw/defender_priors/`
- [x] **T-013.2** Join each shot (by season + `shot_distance_bucket` from T-010.2) to its corresponding league-average FG% prior across defender-distance buckets — if multiple defender-distance buckets exist per shot-distance bucket, use a weighted/blended average as the single `defender_distance_prior` feature value (documented clearly as an approximation) — implemented as summing `fgm`/`fga` across `close_def_dist_range` buckets per (season, shot_dist_range) cell, which is mathematically the attempt-weighted average
- [x] **T-013.3** Save as `data/processed/shots_with_prior.parquet`

---

### T-014 · Assemble Final Feature Table

**Depends on:** T-010, T-011, T-012, T-013
**Context:** Merges every feature stream built so far (geometric, score margin, game-situation, defender prior) into the single table that training will consume, and finalizes categorical encoding.

- [x] **T-014.1** Join all feature tables from T-010, T-011, T-012, T-013 on the shared shot identifier (`GAME_ID` + `GAME_EVENT_ID`) — **deviation:** joined on `GAME_ID` + `GAME_EVENT_ID` + `SEASON` (see the T-009 verification note — a real fan-out bug was caught and fixed this way during integration testing)
- [x] **T-014.2** One-hot or target-encode categorical features (`ACTION_TYPE`, `SHOT_ZONE_BASIC`/`SHOT_ZONE_AREA`, `home_away`) — one-hot (via `pd.get_dummies`), chosen over target encoding to avoid any target-leakage risk
- [x] **T-014.3** Drop rows with unresolved/missing critical features (documenting the drop rate) — also where `is_heave` rows are actually excluded (flagged, not dropped, back in T-010)
- [x] **T-014.4** Attach a `season` label column to every row (needed for the chronological split next) — `SEASON` was attached earlier during T-009 consolidation and carried through every join since; this step just asserts it's present rather than re-deriving it
- [x] **T-014.5** Save the final modeling table to `data/processed/features_final.parquet`

---

### T-015 · Chronological Train/Test Split

**Depends on:** T-014
**Context:** Implements the PRD's core validation decision — train on the two older seasons, test on the most recent — to avoid leakage and produce a defensible evaluation story.

- [x] **T-015.1** Write `pipeline/07_train_test_split.py` that splits `features_final.parquet` into train (rows where `season` is in `TRAIN_SEASONS`) and test (rows where `season == TEST_SEASON`) using the config constants from T-003.1
- [x] **T-015.2** Save `data/processed/train.parquet` and `data/processed/test.parquet`
- [x] **T-015.3** Log basic stats (row counts, overall make-rate) for both splits to catch any obviously broken split (e.g. wildly different base rates) — also raises if either split is empty and warns if make-rates differ by >5%
- **Verification note:** full chain (06→06a→06b→06c→06d→06e→07) run end-to-end against synthetic data; final train/test row counts and make-rates were sane and consistent with the input after the T-014 join fix (see above).

---

## Phase 3 — Model Training & Evaluation

---

### T-016 · Train Naive Baseline Model

**Depends on:** T-015
**Context:** A baseline (predict the league-average FG% for every shot) is required to prove the XGBoost model actually adds value — without it, a "good-looking" log loss number has no reference point.

- [ ] **T-016.1** Write `pipeline/08_train_baseline.py` that computes the overall training-set make rate and applies it as a constant prediction for every test-set shot
- [ ] **T-016.2** Compute log loss, AUC, and Brier score for this baseline on the test set
- [ ] **T-016.3** Save baseline metrics to `models/baseline_metrics.json`

---

### T-017 · Train XGBoost Model

**Depends on:** T-015
**Context:** The core model — gradient-boosted binary classifier predicting make/miss probability from the engineered feature set.

- [ ] **T-017.1** Write `pipeline/09_train_model.py` loading `train.parquet`, separating features from the `SHOT_MADE_FLAG` target
- [ ] **T-017.2** Train an initial XGBoost classifier with reasonable default hyperparameters as a first working model
- [ ] **T-017.3** Confirm the model trains without error and produces sane probability outputs (0-1 range, not degenerate) on a held-out slice of the training data

---

### T-018 · Hyperparameter Tuning

**Depends on:** T-017
**Context:** Improves on the initial default-hyperparameter model using a small, defensible search — not exhaustive, but enough to demonstrate proper ML practice and meaningfully beat the baseline.

- [ ] **T-018.1** Define a small hyperparameter grid (max depth, learning rate, n_estimators, subsample) relevant to XGBoost binary classification
- [ ] **T-018.2** Run cross-validation on the training set only (never touching the test set) to select the best combination, optimizing for log loss
- [ ] **T-018.3** Retrain the final model on the full training set using the selected hyperparameters
- [ ] **T-018.4** Save the tuned model to `models/xgb_shot_quality.json` (XGBoost's native format)

---

### T-019 · Evaluate Model on Test Set

**Depends on:** T-018, T-016
**Context:** Runs the tuned model against the held-out season and compares against the baseline from T-016 — this comparison is the headline result for the Methodology page.

- [ ] **T-019.1** Write `pipeline/10_evaluate_model.py` that scores `test.parquet` with the trained model
- [ ] **T-019.2** Compute log loss (primary), AUC-ROC, and Brier score on the test set
- [ ] **T-019.3** Compare against `models/baseline_metrics.json` and compute the relative improvement
- [ ] **T-019.4** Save all metrics to `models/model_metrics.json`

---

### T-020 · Generate Calibration Curve & Plot

**Depends on:** T-019
**Context:** Visual proof the predicted probabilities are trustworthy — critical since the app displays "expected FG%" directly to users. Built with matplotlib per the PRD's offline-visualization tooling choice.

- [ ] **T-020.1** Bucket test-set predictions into probability bins (e.g. deciles) and compute actual make rate per bin
- [ ] **T-020.2** Plot predicted probability (x-axis) vs. actual make rate (y-axis) against the ideal diagonal, using matplotlib
- [ ] **T-020.3** Save the plot image to `models/calibration_plot.png` and the underlying bucket data to `models/calibration_data.json` (for rendering on the Methodology page later)

---

### T-021 · Generate Feature Importance Chart

**Depends on:** T-018
**Context:** A second transparency artifact for the Methodology page, showing which factors drive the model's predictions (e.g. shot distance and action type should dominate).

- [ ] **T-021.1** Extract feature importances from the trained XGBoost model
- [ ] **T-021.2** Plot a horizontal bar chart of top features using matplotlib
- [ ] **T-021.3** Save the plot to `models/feature_importance.png` and raw values to `models/feature_importance.json`

---

### T-022 · Persist Final Model Artifact & Evaluation Bundle

**Depends on:** T-018, T-019, T-020, T-021
**Context:** Consolidates every training deliverable into one clearly versioned bundle so the scoring step (Phase 4) and the Methodology page (Phase 6) have a single, stable source to read from.

- [ ] **T-022.1** Confirm all artifacts exist: `models/xgb_shot_quality.json`, `models/model_metrics.json`, `models/baseline_metrics.json`, `models/calibration_plot.png`, `models/calibration_data.json`, `models/feature_importance.png`, `models/feature_importance.json`
- [ ] **T-022.2** Write a `models/MODEL_CARD.md` summarizing training date, seasons used, feature list, and headline metrics — for your own reference and portfolio credibility

---

## Phase 4 — Scoring & Database

---

### T-023 · Score All Shots with Trained Model

**Depends on:** T-022, T-014
**Context:** Applies the final trained model to every shot (train + test seasons combined) to produce the `xFG%` value the entire app displays — not just the test set, since the app needs predictions for all 3 seasons of data.

- [ ] **T-023.1** Write `pipeline/11_score_all_shots.py` loading `features_final.parquet` (the full 3-season table) and the trained model from `models/xgb_shot_quality.json`
- [ ] **T-023.2** Generate an `xfg_pct` prediction column for every shot
- [ ] **T-023.3** Save the fully scored dataset to `data/processed/shots_scored.parquet`

---

### T-024 · Design SQLite Schema

**Depends on:** T-014, T-022
**Context:** Defines the tables the Flask app will query. Designed now that the final feature/prediction columns (T-014, T-022) are known, so the schema matches reality instead of being guessed upfront.

- [ ] **T-024.1** Write `db/schema.sql` defining a `shots` table (shot id, player id, season, game id, location, distance, zone, action type, period, time remaining, home/away, score margin, actual make flag, `xfg_pct`)
- [ ] **T-024.2** Define `players` table (player id, name, team(s) per season)
- [ ] **T-024.3** Define `model_metrics` table (metric name, value, season/context) to hold log loss, AUC, Brier score, baseline comparison
- [ ] **T-024.4** Define a `feature_importance` table and a `calibration_bins` table (bin range, predicted midpoint, actual rate, sample count) so the Methodology page can render its charts from the DB rather than static files
- [ ] **T-024.5** Add appropriate indexes (on `player_id`, `season`) anticipating the Player Page and Leaderboard query patterns

---

### T-025 · Write Scored Shots to SQLite

**Depends on:** T-023, T-024
**Context:** Loads the final scored dataset into the actual database file the Flask app will read from at runtime.

- [ ] **T-025.1** Write `pipeline/12_load_db.py` that creates the SQLite file at the configured path using `db/schema.sql`
- [ ] **T-025.2** Insert all rows from `shots_scored.parquet` into the `shots` table
- [ ] **T-025.3** Insert player reference data (from T-004) into the `players` table
- [ ] **T-025.4** Verify row counts in the DB match the source parquet files

---

### T-026 · Write Model Metrics & Artifacts to SQLite

**Depends on:** T-022, T-024
**Context:** Loads the training/evaluation outputs into the DB so the Methodology page can be built as a normal data-driven page instead of reading static JSON files directly (keeps the app's data access pattern consistent).

- [ ] **T-026.1** Insert log loss, AUC, Brier score (model + baseline) from `model_metrics.json`/`baseline_metrics.json` into `model_metrics`
- [ ] **T-026.2** Insert calibration bucket data from `calibration_data.json` into `calibration_bins`
- [ ] **T-026.3** Insert feature importance values from `feature_importance.json` into `feature_importance`
- [ ] **T-026.4** Copy `calibration_plot.png` and `feature_importance.png` into `app/static/images/` so Flask can serve them directly alongside the DB-driven numbers

---

### T-027 · Build Leaderboard Aggregation Table

**Depends on:** T-025
**Context:** Pre-computes per-player, per-season actual FG% vs. expected FG% so the Leaderboard page is a fast, simple query instead of aggregating thousands of shot rows on every page load.

- [ ] **T-027.1** Write `pipeline/13_build_leaderboard_table.py` that groups `shots` by (player, season) and computes total attempts, actual FG%, average `xfg_pct`, and the skill differential (actual − expected)
- [ ] **T-027.2** Also compute the same aggregation across the full 3-year combined sample (per the PRD's "season selector: single season or 3-year combined" requirement)
- [ ] **T-027.3** Write the results to a new `leaderboard` table in the SQLite DB (player id, season or "career", attempts, actual FG%, expected FG%, skill differential)
- [ ] **T-027.4** Flag rows meeting `LEADERBOARD_MIN_ATTEMPTS` with a boolean `qualified` column, so the app can filter without recomputing thresholds at query time

---

### T-028 · Pipeline Integration & Smoke Test

**Depends on:** T-025, T-026, T-027
**Context:** Confirms the full offline pipeline — from raw pull through to a queryable database — works end-to-end before any app code is built on top of it. Catching a broken join or schema mismatch here is far cheaper than debugging it through the Flask layer later.

- [ ] **T-028.1** Write `pipeline/run_all.py` that runs every pipeline script in order (or documents the exact run order) so the whole pipeline is reproducible with one command
- [ ] **T-028.2** Run basic sanity queries directly against the finished SQLite DB: total shot count matches expectations, a sample player's leaderboard row has a plausible actual-vs-expected differential, `model_metrics` table is populated
- [ ] **T-028.3** Document the full pipeline run order and any manual steps in `pipeline/README.md`

---

## Phase 5 — Flask App Foundation

---

### T-029 · Scaffold Flask Application Structure

**Depends on:** T-024
**Context:** Sets up the app skeleton once the DB schema contract (T-024) is known, so routes and templates can be built against a stable schema even while the pipeline (Phase 4) finishes running.

- [ ] **T-029.1** Create `app/` structure: `app/__init__.py` (app factory), `app/routes/`, `app/templates/`, `app/static/`, `app/queries.py`
- [ ] **T-029.2** Implement the Flask app factory pattern (`create_app()`) with basic config loading
- [ ] **T-029.3** Add an entry point `app/run.py` (or `wsgi.py`) to start the dev server
- [ ] **T-029.4** Verify the app boots and serves a trivial "hello" route before building real pages

---

### T-030 · Implement SQLite Query Layer

**Depends on:** T-029, T-024
**Context:** Centralizes all DB access in one module so route handlers stay thin and query logic (joins, filters, aggregations) isn't duplicated across pages.

- [ ] **T-030.1** In `app/queries.py`, implement a connection helper (using Python's built-in `sqlite3`, read-only connection since the app never writes)
- [ ] **T-030.2** Implement `get_player_shots(player_id, season)` — returns shots for a player, optionally filtered by season
- [ ] **T-030.3** Implement `get_leaderboard(season_or_career, min_attempts)` — returns qualified players sorted by skill differential
- [ ] **T-030.4** Implement `get_explorer_shots(season, zone, player_id=None, team_id=None)` — returns filtered shots for the Shot Explorer hexbin
- [ ] **T-030.5** Implement `get_model_metrics()`, `get_calibration_bins()`, `get_feature_importance()` for the Methodology page
- [ ] **T-030.6** Implement `search_players(query)` for the Player Page search box

---

### T-031 · Configure Flask App Settings & Environment

**Depends on:** T-029
**Context:** Keeps environment-specific config (DB path, debug flag) out of hardcoded values, matching best practice and preparing for the eventual Render deployment.

- [ ] **T-031.1** Create `app/config.py` with `DB_PATH`, `DEBUG` settings, loaded from environment variables via `python-dotenv`
- [ ] **T-031.2** Create `.env.example` documenting any configurable variables
- [ ] **T-031.3** Wire config into the app factory from T-029.2

---

### T-032 · Set Up Base Templates & Dark Mode Theme

**Depends on:** T-029
**Context:** Establishes the shared visual shell (nav, base layout, dark NBA/ESPN-inspired styling) once, so every page built afterward inherits consistent styling instead of each page reinventing layout.

- [ ] **T-032.1** Create `app/templates/base.html` with a shared `<head>`, nav placeholder, and content block
- [ ] **T-032.2** Create `app/static/css/main.css` implementing the dark theme: dark background, team-color-friendly accent variables, typography for bold stat callouts
- [ ] **T-032.3** Build a shared nav bar component (links to Landing, Shot Explorer, Leaderboard, Player search, Methodology) included in `base.html`
- [ ] **T-032.4** Verify the base template renders correctly with placeholder content

---

### T-033 · Integrate Plotly.js for Charting

**Depends on:** T-032
**Context:** Sets up the JS charting library once at the app-shell level, since every core page (Explorer, Player, Leaderboard sparkline if any) needs interactive charts.

- [ ] **T-033.1** Add Plotly.js via CDN (or vendored static file) in `base.html`
- [ ] **T-033.2** Build a small reusable JS helper (`app/static/js/hexbin_chart.js`) that takes shot data (x/y court coordinates + xFG%/make flag) and renders a hexbin/heatmap Plotly chart with hover tooltips
- [ ] **T-033.3** Test the helper against a small hardcoded sample dataset to confirm rendering and tooltips work before wiring it to real data

---

## Phase 6 — Core Pages

---

### T-034 · Build Landing Page

**Depends on:** T-032, T-033
**Context:** The entry point users land on first — a brief project intro and links into the three core features, per the PRD's app flow.

- [ ] **T-034.1** Create `app/routes/landing.py` with a `/` route rendering `templates/landing.html`
- [ ] **T-034.2** Write landing copy: project summary, links/cards to Shot Explorer, Leaderboard, Player search, Methodology
- [ ] **T-034.3** Style the landing page using the base theme from T-032

---

### T-035 · Build Shot Explorer — Backend Route & Query

**Depends on:** T-030, T-028
**Context:** Wires the Explorer page's filter controls (season, shot zone, optional player/team) to the `get_explorer_shots` query built in T-030, against the fully populated DB from T-028.

- [ ] **T-035.1** Create `app/routes/explorer.py` with a `/explorer` route accepting query params: `season`, `zone`, `player_id`, `team_id`
- [ ] **T-035.2** Call `get_explorer_shots()` with the parsed filters; default to league-wide aggregate when no player/team is selected
- [ ] **T-035.3** Return shot data as JSON (for the frontend chart to consume via fetch) plus render the page shell with filter dropdowns populated from the DB (season list, zone list, player list)

---

### T-036 · Build Shot Explorer — Hexbin Visualization & Filters

**Depends on:** T-035, T-033
**Context:** The frontend half of the Explorer — renders the hexbin chart using the helper from T-033 and wires up the filter controls to re-fetch and re-render.

- [ ] **T-036.1** Create `templates/explorer.html` extending `base.html`, with filter dropdowns (season, zone, player/team) and a chart container
- [ ] **T-036.2** On filter change, fetch updated shot data from the `/explorer` JSON endpoint and re-render the hexbin chart via `hexbin_chart.js`
- [ ] **T-036.3** Confirm hover tooltips show shot distance, action type, `xfg_pct`, and actual result per the PRD spec
- [ ] **T-036.4** Manually test all filter combinations for correctness (empty states, single-player view, full league view)

---

### T-037 · Build Leaderboard — Backend Route & Query

**Depends on:** T-030, T-027, T-028
**Context:** Serves the pre-aggregated leaderboard table (T-027) filtered by qualification threshold and season scope.

- [ ] **T-037.1** Create `app/routes/leaderboard.py` with a `/leaderboard` route accepting a `season` query param (specific season or `"career"` for the 3-year combined view)
- [ ] **T-037.2** Call `get_leaderboard()` filtered to `qualified = true` rows, sorted by skill differential descending
- [ ] **T-037.3** Render the page with the ranked table and a season selector control

---

### T-038 · Build Leaderboard — Frontend & Season Selector

**Depends on:** T-037, T-032
**Context:** Presents the ranked list clearly and links each row to the corresponding Player Page, completing the leaderboard→player navigation flow from the PRD.

- [ ] **T-038.1** Create `templates/leaderboard.html` rendering the ranked table (rank, player name, attempts, actual FG%, expected FG%, differential)
- [ ] **T-038.2** Wire the season selector to reload the page/route with the chosen season param
- [ ] **T-038.3** Make each player row a link to `/players/<player_id>`
- [ ] **T-038.4** Style using the base theme; highlight top/bottom performers with accent colors

---

### T-039 · Build Player Page — Search & Backend Route

**Depends on:** T-030, T-028
**Context:** Implements player lookup (via search or direct link from the Leaderboard) and the data query for a single player's shot profile.

- [ ] **T-039.1** Create `app/routes/player.py` with a `/players/<player_id>` route, optional `season` query param
- [ ] **T-039.2** Call `get_player_shots()` and compute the player's actual FG% vs. average `xfg_pct`, overall and broken down by shot zone
- [ ] **T-039.3** Implement a `/players/search?q=` endpoint calling `search_players()`, returning JSON matches for a search-as-you-type box
- [ ] **T-039.4** Handle the "player not found" / "no shots in this season" edge cases gracefully

---

### T-040 · Build Player Page — Shot Chart & Actual vs. Expected Breakdown

**Depends on:** T-039, T-033
**Context:** The frontend half of the Player Page — visualizes the individual player's shot profile and the actual-vs-expected comparison called out as a core PRD feature.

- [ ] **T-040.1** Create `templates/player.html` with a search box (wired to the `/players/search` endpoint), season filter, hexbin shot chart (via `hexbin_chart.js`), and a stats panel
- [ ] **T-040.2** Render the actual vs. expected FG% comparison overall and per shot zone (table or small bar chart)
- [ ] **T-040.3** Wire the season filter to reload data without a full page navigation (fetch + re-render, consistent with the Explorer pattern)
- [ ] **T-040.4** Manually test with a high-volume player and a low-volume/edge-case player

---

### T-041 · Build Methodology Page — Backend Route

**Depends on:** T-026, T-030
**Context:** Serves the model transparency data (metrics, calibration bins, feature importance) from the DB tables populated in T-026.

- [ ] **T-041.1** Create `app/routes/methodology.py` with a `/methodology` route calling `get_model_metrics()`, `get_calibration_bins()`, `get_feature_importance()`
- [ ] **T-041.2** Pass the static plot image paths (`calibration_plot.png`, `feature_importance.png` from T-026.4) into the template context as a fallback/complement to any interactive charts

---

### T-042 · Build Methodology Page — Frontend

**Depends on:** T-041, T-020, T-021, T-032
**Context:** Presents the model's validation story clearly — this is the page that carries the "demonstrate modeling skill" goal of the whole project, so it needs to read cleanly to a technical reviewer.

- [ ] **T-042.1** Create `templates/methodology.html` displaying headline metrics (log loss, AUC, Brier score) with the baseline comparison from T-019.3 shown side-by-side
- [ ] **T-042.2** Render the calibration plot (image or Plotly-rendered from `calibration_bins` data) and feature importance chart
- [ ] **T-042.3** Write the plain-language section explaining data limitations (no true per-shot defender distance/shot clock, use of `ACTION_TYPE` as contest proxy, league-average prior approximation) per the PRD's transparency requirement
- [ ] **T-042.4** Style consistently with the base theme

---

## Phase 7 — Navigation & Cross-Page Integration

---

### T-043 · Implement Global Navigation & Cross-Links

**Depends on:** T-034, T-036, T-038, T-040, T-042
**Context:** Wires together the individual pages into the coherent app flow specified in the PRD (Landing → Explorer/Leaderboard → Player Page, Methodology reachable from anywhere).

- [ ] **T-043.1** Finalize the nav bar (from T-032.3) with active-page highlighting across all 5 pages
- [ ] **T-043.2** Verify Explorer's player-select interaction can deep-link into the Player Page (per PRD app flow diagram)
- [ ] **T-043.3** Verify Leaderboard row clicks correctly route to the matching Player Page with data loaded
- [ ] **T-043.4** Add a consistent footer/credit linking to Methodology from every page

---

## Phase 8 — Design & Polish

---

### T-044 · Full Dark Mode / NBA-Styling Pass

**Depends on:** T-043
**Context:** With all pages functionally wired together, do a dedicated visual consistency pass — this is where the "looks like a real app" goal gets delivered.

- [ ] **T-044.1** Audit all 5 pages against the theme variables from T-032.2 for consistent spacing, color usage, and typography
- [ ] **T-044.2** Add team-colored accents where relevant (e.g. player page header tinted by team color)
- [ ] **T-044.3** Polish stat callouts (large bold numbers for FG%, differential) to match the ESPN/NBA.com-inspired aesthetic from the PRD

---

### T-045 · Responsive/Desktop Layout QA

**Depends on:** T-044
**Context:** Confirms the desktop-first layout doesn't visibly break at smaller widths, per the PRD's "responsive enough not to break, not mobile-optimized" requirement.

- [ ] **T-045.1** Test all 5 pages at common desktop widths (1920px, 1440px, 1280px)
- [ ] **T-045.2** Test at a tablet width (~768px) and confirm no broken/overlapping layout, even if not fully optimized
- [ ] **T-045.3** Fix any critical breakage found (overflow, unreadable text, non-functional filters) — cosmetic-only mobile issues can be deferred

---

### T-046 · Cross-Browser & Manual QA Pass

**Depends on:** T-045
**Context:** Final functional check across the whole app before deployment — catches interaction bugs (broken filters, chart rendering issues) that unit-level work wouldn't surface.

- [ ] **T-046.1** Manually walk through the full app flow (Landing → Explorer → Leaderboard → Player Page → Methodology) in at least two browsers (e.g. Chrome, Safari/Firefox)
- [ ] **T-046.2** Verify all interactive features: hexbin hover tooltips, season/zone filters, player search, leaderboard season selector, leaderboard→player links
- [ ] **T-046.3** Fix any bugs found; re-test affected flows after fixes

---

## Phase 9 — Deployment

---

### T-047 · Prepare Production Configuration

**Depends on:** T-046
**Context:** Gets the app ready to run under a production WSGI server rather than Flask's dev server, and finalizes the deployment-specific files Render needs.

- [ ] **T-047.1** Install and configure `gunicorn` as the production WSGI server
- [ ] **T-047.2** Finalize `requirements.txt` with all app + pipeline dependencies pinned
- [ ] **T-047.3** Create the Render service definition (`render.yaml` or configure via dashboard) with the correct start command (`gunicorn app.run:app` or equivalent)
- [ ] **T-047.4** Confirm the SQLite DB file (populated by the offline pipeline) is included in the deployment bundle, since Render's free-tier disk is ephemeral and the app never writes to it at runtime

---

### T-048 · Deploy to Render

**Depends on:** T-047
**Context:** Ships the app to a public URL — the final deliverable for the portfolio piece.

- [ ] **T-048.1** Push the repository to GitHub (if not already) and connect it to a new Render web service
- [ ] **T-048.2** Trigger the first deploy; resolve any build/start failures
- [ ] **T-048.3** Confirm the live URL loads the Landing page successfully

---

### T-049 · Production Smoke Test

**Depends on:** T-048
**Context:** Final verification that everything works identically in production as it did locally — the last task before calling the project done.

- [ ] **T-049.1** Repeat the manual QA walkthrough from T-046 against the live production URL
- [ ] **T-049.2** Verify page load times are reasonable (SQLite reads should be fast; flag anything sluggish)
- [ ] **T-049.3** Share/record the final live link for the portfolio
