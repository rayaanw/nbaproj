# Model Card — NBA Shot Quality Model

**Training date:** 2026-07-20
**Seasons used:** train=['2022-23', '2023-24'], test=2024-25 (chronological split, all seasons: ['2022-23', '2023-24', '2024-25'])
**Algorithm:** XGBoost binary classifier (make/miss)
**Feature count:** 74

## Headline metrics (test season)

| Metric | Model | Baseline (constant prediction) | Improvement |
|---|---|---|---|
| Log loss | 0.6372 | 0.6914 | 7.8% |
| AUC-ROC | 0.6596 | 0.5 | — |
| Brier score | 0.2242 | 0.2491 | — |

## Top feature importances (gain)

| Feature | Importance |
|---|---|
| SHOT_DISTANCE | 451.03 |
| SHOT_ZONE_BASIC_Above the Break 3 | 317.80 |
| ACTION_TYPE_Tip Layup Shot | 216.77 |
| ACTION_TYPE_Running Dunk Shot | 197.20 |
| ACTION_TYPE_Cutting Dunk Shot | 184.06 |
| ACTION_TYPE_Driving Layup Shot | 139.90 |
| ACTION_TYPE_Alley Oop Dunk Shot | 112.09 |
| ACTION_TYPE_Dunk Shot | 82.40 |

## Feature list

`PERIOD, MINUTES_REMAINING, SECONDS_REMAINING, SHOT_DISTANCE, LOC_X, LOC_Y, shot_angle, defender_distance_prior, score_margin, time_remaining_in_period, period_clean, is_overtime, ACTION_TYPE_Alley Oop Dunk Shot, ACTION_TYPE_Alley Oop Layup shot, ACTION_TYPE_Cutting Dunk Shot, ACTION_TYPE_Cutting Finger Roll Layup Shot, ACTION_TYPE_Cutting Layup Shot, ACTION_TYPE_Driving Bank Hook Shot, ACTION_TYPE_Driving Dunk Shot, ACTION_TYPE_Driving Finger Roll Layup Shot, ACTION_TYPE_Driving Floating Bank Jump Shot, ACTION_TYPE_Driving Floating Jump Shot, ACTION_TYPE_Driving Hook Shot, ACTION_TYPE_Driving Layup Shot, ACTION_TYPE_Driving Reverse Dunk Shot, ACTION_TYPE_Driving Reverse Layup Shot, ACTION_TYPE_Dunk Shot, ACTION_TYPE_Fadeaway Bank shot, ACTION_TYPE_Fadeaway Jump Shot, ACTION_TYPE_Finger Roll Layup Shot, ACTION_TYPE_Floating Jump shot, ACTION_TYPE_Hook Bank Shot, ACTION_TYPE_Hook Shot, ACTION_TYPE_Jump Bank Shot, ACTION_TYPE_Jump Shot, ACTION_TYPE_Layup Shot, ACTION_TYPE_Pullup Jump shot, ACTION_TYPE_Putback Dunk Shot, ACTION_TYPE_Putback Layup Shot, ACTION_TYPE_Reverse Dunk Shot, ACTION_TYPE_Reverse Layup Shot, ACTION_TYPE_Running Alley Oop Dunk Shot, ACTION_TYPE_Running Alley Oop Layup Shot, ACTION_TYPE_Running Dunk Shot, ACTION_TYPE_Running Finger Roll Layup Shot, ACTION_TYPE_Running Jump Shot, ACTION_TYPE_Running Layup Shot, ACTION_TYPE_Running Pull-Up Jump Shot, ACTION_TYPE_Running Reverse Dunk Shot, ACTION_TYPE_Running Reverse Layup Shot, ACTION_TYPE_Step Back Bank Jump Shot, ACTION_TYPE_Step Back Jump shot, ACTION_TYPE_Tip Dunk Shot, ACTION_TYPE_Tip Layup Shot, ACTION_TYPE_Turnaround Bank Hook Shot, ACTION_TYPE_Turnaround Bank shot, ACTION_TYPE_Turnaround Fadeaway Bank Jump Shot, ACTION_TYPE_Turnaround Fadeaway shot, ACTION_TYPE_Turnaround Hook Shot, ACTION_TYPE_Turnaround Jump Shot, SHOT_ZONE_BASIC_Above the Break 3, SHOT_ZONE_BASIC_In The Paint (Non-RA), SHOT_ZONE_BASIC_Left Corner 3, SHOT_ZONE_BASIC_Mid-Range, SHOT_ZONE_BASIC_Restricted Area, SHOT_ZONE_BASIC_Right Corner 3, SHOT_ZONE_AREA_Back Court(BC), SHOT_ZONE_AREA_Center(C), SHOT_ZONE_AREA_Left Side Center(LC), SHOT_ZONE_AREA_Left Side(L), SHOT_ZONE_AREA_Right Side Center(RC), SHOT_ZONE_AREA_Right Side(R), home_away_away, home_away_home`

## Data limitations

See `PRD-NBAShotQualityModel.md` and `CLAUDE.md` for the full discussion. In short:
`ACTION_TYPE` is the primary real per-shot contest proxy (true defender distance/shot
clock/contested-shot flag are not exposed by nba_api's public endpoints);
`defender_distance_prior` is a league-average approximation joined by
(season, shot distance bucket), not true per-shot tracking data.
