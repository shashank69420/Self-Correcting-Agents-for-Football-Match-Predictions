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
- Gate B: FAILED (2026-10-19). c_att +0.0950 CI [0.0487, 0.1413];
  c_def -0.0022 CI [-0.0413, 0.0368]. Final for the locked spec. Code and
  details are on branch gate-b-lineup.

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

## Failure protocol
Trigger: a gate fails, an expected number moves, a test fails, or a result
contradicts the written expectation.
1. Stop changing code. Do not retry with other settings to flip a result.
2. Run /diagnose. It is read-only plus descriptive checks.
3. Classify the cause with evidence: (a) implementation bug (code disagrees
   with the written spec); (b) data problem (coverage, join, leakage);
   (c) true null or underpowered; (d) spec problem (gate or proxy badly chosen).
4. Act by class:
   - (a) Fix only if you can show the code disagrees with the spec; add a
     regression test; confirm expected numbers are unchanged.
   - (b) Fix if the fix is spec-neutral, otherwise stop and ask.
   - (c) and (d) Report. Do not change the spec. Offer options tagged
     [pre-registered] or [post-hoc] with one recommendation.
5. Never without my explicit approval: change a locked spec item, threshold
   or gate; use test-period data in any decision; change an expected number;
   run more than one post-hoc specification per gate; edit files outside your
   ownership.
6. Log every deviation, failed gate and post-hoc run in DECISIONS.md with
   date, what was decided, and who approved it.
7. Post-hoc results are labelled EXPLORATORY in every printout, report and
   commit message. A gate verdict is never overwritten.

## Definition of done
- Before any report or commit that says finished, run `python -X utf8 tools/gate.py` and paste its final block
  (the check lines and the GATE verdict). `--fast` skips the anchor run and is for commits only.
- Never report done on a FAIL. On a FAIL, run /diagnose on the failing lines.
- The gate checks facts, not interpretations: it cannot tell whether a conclusion is right.
- Never edit the anchors in tools/gate.py, tools/ownership.txt or results/claims.json to make the gate pass
  without the user's explicit approval.

## Forward logger
- `python -X utf8 forward_logger.py` logs upcoming fixtures; `--verify` checks the log; `--score` scores it and
  regenerates forward/score_report.md. The rules are in forward/PREREGISTRATION.md (committed before the first log).
- Cache exception (approved 2026-10-26): the forward logger may read the completed seasons 2019-2020 to 2025-2026
  from data/fixtures_raw.pkl. The 2026-2027 results and the fixture list are always fetched fresh.
- forward/predictions.jsonl is append-only and hash-chained, and only forward_logger.py writes it. Never hand-edit,
  reorder, truncate or rewrite it. Run `--verify` before committing it.
- Never change the P1 params (results/experiments/candidate_p1.json), the baseline params, home_adv or the forecast
  code after the first log (2026-10-26). A changed model gets a new model id and is logged separately.
- `--score` never modifies predictions.jsonl. Below 600 scored matches the report is descriptive only.
