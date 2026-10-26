# P2 pre-registration

Written and committed on 2026-10-26, before any data from seasons 2014-2015 to 2018-2019 was fetched. Branch p2.
Nothing in this file changes after the commit "p2: preregistration". No parameter, row or rule changes after Phase 4
(freeze).

## Purpose
Add evidence and accuracy without spending TEST: replicate the frozen P1 on four never-examined seasons, test three
pre-registered improvements selected on DEV/VAL only, then confirm the frozen candidates once on the fresh seasons.

## Starting point
- P1 = `results/experiments/candidate_p1.json`: overrides of `exp_model.DEFAULT_PARAMS` process_noise 0.005,
  initial_var 0.3, cold_defence 0.3, clip_rates on, rho -0.04 (cold_attack 0, no drift, no league effects,
  no calibration). Preflight confirmed it equals the accepted E1 + E3 + E5 choices in `results/experiments/`.
- Stage 2 baseline = `exp_model.DEFAULT_PARAMS`.
- home_adv = `stage2_dynamic.compute_home_adv(train_df, test_df)` on the main 2019-2026 data (the fixed value every
  earlier stage uses). The same fixed value is used for every run in P2, including the fresh seasons; it is not
  re-estimated on any fresh row.

## Windows (locked)
Main data (`data_pipeline`, 19,145 rows), the P1 split:
- BURN-IN: before 2020-07-01. Filtered, never scored.
- DEV: 2020-07-01 to 2023-06-30.
- VAL: from 2023-07-01, excluding TEST_INDEX (`test_df.index`). TEST rows are excluded by row identity.
- Selection runs the filter on the non-TEST rows only. No metric, table or plot on TEST_INDEX rows until Phase 6.

FRESH (F): seasons 2014-2015 to 2018-2019, the 8 leagues in `data_pipeline.LEAGUES`, fetched with penaltyblog
`FootballData`, run as its own chronological sequence (teams start fresh; no state carried from or to the main data).
- 2014-2015 is burn-in and is never scored. 2015-2016 to 2018-2019 are scored (every row of those seasons).
- Cleaning is exactly `data_pipeline`'s: concatenate league-major then season, drop rows missing goals_home,
  goals_away or datetime, `date = pd.to_datetime(datetime)`, `sort_values('date')`, `reset_index(drop=True)`.
- Single pre-registered exception: a league-season file that has no Time column (football-data added kickoff times
  in 2019-2020, so penaltyblog builds no `datetime` for older files) gets `datetime = Date` at 00:00 for that
  league-season. Files with a Time column are untouched (rows with an unparseable time are dropped, as in
  `data_pipeline`). Matches on the same day are then ordered by the same sort; a team plays at most once a day.
- A league-season is dropped only if it cannot be fetched, and that is reported. If more than 10% of the 40
  league-seasons (more than 4) are missing: STOP.
- No season after 2018-2019 may enter F (asserted in code).

## Model code
`p2_model.run_filter(df, params, home_adv)`: the Stage 2 / exp_model loop built from exp_model's and Stage 2's
helpers (`make_params`, `dixon_coles_probs`, `TeamState`, `predict_step`, `update_step`), no copied maths. `params` is
an exp_model parameter set plus `shots_w` (default 0). Drift, season variance and league effects are not supported
(not used by P1 or any P2 candidate; the function raises if they are set). Gate: with shots_w = 0 and P1 parameters it
must reproduce `exp_model.run_filter` P1 forecasts on all 19,145 rows to 1e-12, else STOP.

## Selection family (fixed; run in this order, each on top of the incumbent; P1 at the start)

### S0: widened grid on P1
process_noise in {0.0025, 0.005} x initial_var in {0.15, 0.3} x cold_defence in {0.3, 0.45, 0.6}; clip_rates on,
rho -0.04, cold_attack 0. 12 candidates, enumerated in that nesting order (process_noise outermost). P1 is one of
them.

### S1: shots on target in the update
The post-match update uses y_eff = (1 - w) * goals + w * c * SoT for each side, w in {0.25, 0.5, 0.75} (w = 0 is the
incumbent). Columns: SoT home = `hst`, SoT away = `ast`.
- c (goals per shot on target) for a row = (sum of home + away goals) / (sum of hst + ast) over matches of that
  row's league dated strictly before the row's date (same-day matches excluded) in the frame being filtered, using
  only matches with both hst and ast present; at least 300 such matches. Otherwise the same ratio pooled over all
  leagues strictly earlier, at least 300 matches. Otherwise w = 0 for that row.
- A row with SoT missing for either team gets w = 0 (both sides use goals).
- Shots enter only the post-match update, never the forecast of the same match. The gradient is y_eff minus the
  pre-match rate; the Fisher information (the pre-match rate) is unchanged. This is `stage2_dynamic.update_step`
  called with y_eff in place of the goals.
- "The frame being filtered" is the non-TEST main frame for selection, the full main frame for Phase 6, and the F
  frame for Phase 5. Because c uses strictly earlier rows only, the forecasts of earlier rows are identical across
  these frames.

### S2: stack with the market (separate Model+Market track)
On the incumbent goals-only model after S0 and S1:
z_k = a * log p_model_k + b * log m_k + c_k, probabilities = softmax(z), k in (home, draw, away).
- m = the overround-removed (proportional, m_k = (1/o_k) / sum_j(1/o_j)) pre-match snapshot odds triple.
- c has mean zero: c = (c1, c2, -c1 - c2).
- Fit a, b, c by minimising mean log-loss on DEV rows with snapshot odds (model log-probabilities clipped at 1e-15,
  as in `exp_model.apply_calibration`). BFGS with analytic gradient from a = 0, b = 1, c = 0.
- Comparator "market-only": z_k = b * log m_k + c_k, fitted the same way (from b = 1, c = 0).
- Snapshot triple: the non-closing average-odds triple (`avg_h, avg_d, avg_a`) if its missing share on DEV is under
  5%, else Bet365 non-closing (`b365_h, b365_d, b365_a`). Measured at preflight from coverage only: avg triple missing
  on 0.34% of DEV rows, so the snapshot triple is `avg_h, avg_d, avg_a`.
- On F: the same named columns where present. Football-data's pre-2019 files carry the average non-closing odds as
  Betbrain averages (BbAvH, BbAvD, BbAvA; penaltyblog names `bb_av_h, bb_av_d, bb_av_a`). For a F league-season
  without `avg_*` columns, the snapshot triple is `bb_av_*`. If neither exists on F: STOP (no snapshot odds).
- A row has snapshot odds when all three odds are numeric and > 1.
- Never use a closing column (a C after the bookmaker code, e.g. `avg_ch`, `psch`) as an input.

## Selection rule (per experiment)
Pick the lowest DEV log-loss candidate (first minimum in grid order). Accept only if all three hold:
(i) DEV log-loss improves on the incumbent, (ii) VAL log-loss improves, (iii) the 99% paired week-block bootstrap CI
(2000 resamples, seed 20261030; `exp_harness.week_block_ci`) on DEV+VAL rows for (candidate minus incumbent) per-row
log-loss has upper bound below 0. A candidate equal to the incumbent fails (i).
For S2 the comparison is stack minus market-only, both fitted on DEV, on rows with snapshot odds: (i) on DEV rows,
(ii) on VAL rows, (iii) on DEV+VAL rows. No re-running with other grids.

## Freeze (Phase 4)
`results/p2/candidate_p2.json`: the accepted goals-only parameters (P1 overrides plus accepted S0/S1 values, w), the
stack and market-only coefficients refitted on DEV+VAL snapshot rows, the snapshot triple and its column names on the
main data and on F, the S0/S1/S2 verdicts, and the sha256 of the file's own content (computed with the hash field
empty). If S2 is rejected the refitted coefficients are still frozen, for the descriptive Phase 6 table only.
The function that scores F rows raises unless this file exists and is committed unchanged.

## Primary tests on F (once, after freezing)
Rows: every F row in seasons 2015-2016 to 2018-2019. Metric: mean per-match log-loss. CI: paired week-block bootstrap
(calendar weeks, 2000 resamples, seed 20261030) at level 1 - 0.05/3 (98.3%, Bonferroni for three tests); a test passes
only if the upper bound of (first minus second) is below 0. The level stays at 98.3% whichever tests run.
- T-A: P1 minus Stage 2 baseline (replication).
- T-B: final goals-only candidate minus P1. Run only if S0 or S1 was accepted.
- T-C: stack minus market-only, on scored F rows with snapshot odds. Run only if S2 was accepted.

Secondary and descriptive: RPS, Brier, accuracy, per season and per league, and the gap to the closing market on F
rows that have one: the closing average (`avg_ch`) if present, else Pinnacle closing (`psch, pscd, psca`), bookmaker
labelled. It is not compared with the TEST-era market figures.

## Phase 6 (descriptive only, after the fresh write-up)
Frozen candidates scored on TEST_INDEX with the lower-level helpers used for `results/experiments/test_once`
(`exp_harness.row_scores`, `market_probs`, `week_block_ci`, `metrics.probability_metrics`). Every table is labelled
"DESCRIPTIVE: TEST is not fresh; no claim from this". Rows: baseline, P1, final goals-only candidate, stack,
market-only (snapshot), closing market.

## Tests
`tests/test_p2.py`, synthetic data, no network: w = 0 reproduces P1; the shots scale uses only strictly earlier data;
a missing SoT gives w = 0; the stack with a = 0 equals market-only; the stack fit uses DEV rows only; the F scoring
guard raises without the frozen file; no TEST_INDEX row reaches any selection frame; the acceptance rule rejects when
VAL worsens; the fresh set contains no season after 2018-2019.

## Stop conditions
An anchor moves; the w = 0 equality fails; no snapshot odds exist on F or DEV; a leak cannot be resolved; a step needs
a file outside the session exceptions; the gate fails on anything but the branch check after 3 attempts.
