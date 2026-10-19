# Football Match Prediction (B12)

Bayesian sequential model for football match outcomes, with two extensions:
a surprise-based update (negative result, kept for the record) and lineup
weighting (under test). Solo project. The presentation is a retrospective
backtest plus a forward test on 2026-27.

## Environment
- Windows, Python venv at venv/. Activate it before running anything.
- penaltyblog is pinned to 1.12.3. Do not upgrade it.

## Layout
- main.py: orchestrates stages. `python main.py` runs the baseline.
  `--audit` runs the Transfermarkt matching audit (slow, downloads data).
  `--refresh` re-ingests fixtures instead of using the cache.
- data_pipeline.py: fixture ingestion, cache, cleaning, 80/20 chronological split.
- stage1_baseline.py: static Dixon-Coles (penaltyblog).
- stage2_dynamic.py: sequential Bayesian filter (TeamState, predict_step, update_step).
- stage3_detector.py: change detector, prepare_lineup_offsets, run_change_filter.
- metrics.py: RPS, Brier, log-loss, bootstrap helpers.
- lineup_audit.py: Transfermarkt matching and starting-XI audit.
- main_original.py: frozen backup. Do not edit.

## Expected numbers (must hold after any change)
- Stage 1 RPS 0.2057, Stage 2 RPS 0.2060 on 3545 common test matches.
- Stage 2 RPS on all 3829 held-out matches: 0.2059.
- Selected CHANGE_SCALE: 0.
- Test period: 3829 fixtures, Gate A passed (100% matched, >= 90% full XI).
If a change moves any of these, stop and report. Do not update the numbers.

## Hard rules
- Do not change formulas, constants, or printed output in Stages 1-3 or metrics.
- No post-match information in any feature. Lineups: starting XI only,
  available 60 minutes before kickoff. Market values: last valuation strictly
  before the match date. Never use players.market_value_in_eur (current value).
- Tune and estimate on training data only. Test-period results are
  retrospective; label them that way.
- No globals(). Pass values as function arguments.
- No /content/ paths. Outputs go to outputs/. Downloads and cache go to data/.
- Never commit data/, outputs/, venv/, or *.csv.
- The forward logger must always fetch fresh data, never the cache.

## Gates
- Gate A (test-period lineup coverage >= 90% full XI): PASSED.
- Gate B (Poisson GLM on training data: c_att > 0 and c_def < 0, both 95% CIs
  exclude zero): NOT YET RUN. If it fails, stop and report a validated null.
  Do not build the adjustments file.

## Lineup estimation rules
- Estimation cutoff: ESTIMATION_CUTOFF = TEST_START - 24 hours. Gate B and
  any fitting use only matches dated before this cutoff.
- Burn-in filter (estimation only, not applied to the adjustments file):
  exclude a match if either team has fewer than 10 prior appearances in the
  full dataset, or if lambda_home or mu_away is outside [0.15, 6.0]. Print
  the number dropped, per season.
- Features: starting XI only (type = starting lineup). Attack line = midfield
  plus attack positions; defence line = goalkeeper plus defender positions.
  Verify the position values by printing them before mapping. Player value =
  last valuation strictly before the match date. Team usual = mean of that
  team's previous 10 matches, requiring at least 5, otherwise missing.
  A and D = log ratio against usual, winsorized to [-1, 1].
- Adjustments: delta = clip(coefficient * feature, -0.5, 0.5). Rows only for
  fixtures with date >= TEST_START and complete features.
- Asserts before saving the adjustments file: no row with date < TEST_START;
  available_at < date for every row (available_at = date - 60 minutes); no
  NaN; (team_home, team_away, date) unique.

## Git
- Setup commits may go straight to main. From Session A and B onward, one
  branch per task. Commit after each working step.
- Commit message format: "<area>: <what changed>".
- Never force-push. Never amend a pushed commit.
- Run python main.py and confirm the expected numbers before every commit.

## Parallel work
Work is split across sessions in separate worktrees. See PLAN.md for each
session's files and tasks. Only edit files in your session's ownership list.
Never run git checkout, switch, merge, or worktree commands; the user merges.
