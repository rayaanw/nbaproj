# Pipeline — Run Order & Manual Steps

Every script here is numbered in run order. `run_all.py` runs the whole
sequence for you (see below), but each script can also be run standalone —
useful for resuming after a partial failure or rerunning just one stage
after a code change.

## Prerequisites

- `python -m venv venv && source venv/bin/activate && pip install -r ../requirements.txt`
- macOS only: `brew install libomp` (XGBoost needs it — see the repo root `CLAUDE.md`)
- Network access to `stats.nba.com` for steps 01-04 (some sandboxed/CI
  environments block this host — run from a machine with normal internet
  access if `curl -m 5 https://stats.nba.com/...` times out)

## One-command run

```bash
python pipeline/run_all.py
```

This is slow — rate-limited `nba_api` calls across 3 seasons of shot data
and per-game play-by-play, likely 1-3+ hours depending on how aggressively
`stats.nba.com` throttles that day. It's resumable: if it dies partway
through, just rerun it — steps 01-04 skip any (player, season)/game/season
that's already been pulled (see each script's own resumability logic), and
later steps simply overwrite their own output on rerun.

## Full run order

| # | Script | Implements | Notes |
|---|---|---|---|
| 1 | `01_pull_player_reference.py` | T-004 | Determines the qualifying player/season scope |
| 2 | `02_pull_shot_charts.py` | T-005 | Slowest step — one API call per (player, season) |
| 3 | `03_pull_playbyplay.py` | T-006 | One API call per distinct game; needs some shot files pulled first |
| 4 | `04_pull_defender_distance_priors.py` | T-007 | League-wide aggregates, ~28 calls/season. **Verify the `SHOT_DIST_RANGES`/`CLOSE_DEF_DIST_RANGES` filter strings in this script against a live call before trusting a full run** — see the module docstring |
| 5 | `05_validate_raw_data.py` | T-008 | Schema/null-rate checks + writes `data/raw/manifest.json` |
| 6 | `06_consolidate_shots.py` | T-009 | Merges all raw shot files into one table |
| 7 | `06a_geo_features.py` | T-010 | Shot angle, distance bucket, heave flag |
| 8 | `06b_score_margin.py` | T-011 | Joins score margin from play-by-play |
| 9 | `06c_context_features.py` | T-012 | Time remaining, home/away, period |
| 10 | `06d_defender_prior.py` | T-013 | Joins the league-average defender-distance prior |
| 11 | `06e_assemble_features.py` | T-014 | Final joined + one-hot-encoded feature table |
| 12 | `07_train_test_split.py` | T-015 | Chronological split (train = 2 oldest seasons, test = newest) |
| 13 | `08_train_baseline.py` | T-016 | Constant-prediction baseline |
| 14 | `09_train_model.py` | T-017/T-018 | Trains + tunes the XGBoost model |
| 15 | `10_evaluate_model.py` | T-019 | Test-set metrics vs. baseline |
| 16 | `10a_calibration_plot.py` | T-020 | Calibration curve |
| 17 | `10b_feature_importance.py` | T-021 | Feature importance chart |
| 18 | `10c_write_model_card.py` | T-022 | `models/MODEL_CARD.md` + artifact bundle check |
| 19 | `11_score_all_shots.py` | T-023 | Scores every shot (train + test) with the final model |
| 20 | `12_load_db.py` | T-025 | Creates `db/*.sqlite3` from `db/schema.sql`, loads shots + players |
| 21 | `12a_load_model_artifacts.py` | T-026 | Loads model metrics/calibration/importance into the DB, copies plot images to `app/static/images/` |
| 22 | `13_build_leaderboard_table.py` | T-027 | Pre-aggregates the `leaderboard` table |

### Why some steps aren't top-level-numbered

Only `06_consolidate_shots.py` and `07_train_test_split.py` (and similarly
`10_evaluate_model.py`/`11_score_all_shots.py`/`12_load_db.py`/
`13_build_leaderboard_table.py`) have prescribed filenames in `todo.md`. The
feature-engineering steps in between (T-010-T-014) and the
calibration/importance/model-card steps (T-020-T-022) don't, so they're
numbered with letter suffixes (`06a`-`06e`, `10a`-`10c`) to sit clearly
between the fixed scripts while still sorting in run order.

## After the pipeline finishes

`db/*.sqlite3` is now populated and the Flask app can serve from it:

```bash
python app/run.py
```

## If something goes wrong mid-run

- Check `data/raw/shots/_failures.log` and `data/raw/playbyplay/_failures.log`
  for any (player, season)/game that errored out after retries — rerun the
  corresponding pull script to retry just those.
- `05_validate_raw_data.py` can be rerun any time to sanity-check what's been
  pulled so far without needing the whole pull to be complete.
- Every step past `06_consolidate_shots.py` fully overwrites its own output
  parquet/table on rerun, so there's no partial-state risk once raw pulls are
  done — just rerun from wherever you want to restart.
