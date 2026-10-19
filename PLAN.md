# PLAN.md

## Goal
Finish B12: lineup gate result, four-way comparison, forward log running.

## Session A: gate-b-lineup (worktree b12-lineup)
Owns:
- lineup.py (new)
- stage3_detector.py: prepare_lineup_offsets and load_lineup_adjustments only
- main.py: lineup block only
- tests/test_lineup.py (new)

Tasks, in order:
1. Lineup features: attack-line and defence-line market value from starting
   XI only, valuations strictly before match date, log ratio against the
   team's previous 10 matches, winsorized to [-1, 1].
2. Gate B: Poisson GLM on training data, Stage 2 expected goals as offset,
   burn-in filter from CLAUDE.md, cluster-robust SE by match. Print
   GATE B: PASSED or FAILED with reason.
3. Only if Gate B passed: adjustments file for test-period fixtures, with the
   asserts in CLAUDE.md.
4. Baseline vs Baseline+lineup on identical test rows. LogLoss primary,
   paired week-block bootstrap CI.
5. Four-way table.

Done when: Gate B is reported, the commit is made, and if Gate B passed,
the four-way table is printed.
If Gate B fails: commit the feature code and the failing result. Do not
run steps 3 to 5.

## Session B: forward-logger (worktree b12-forward)
Owns:
- forward_logger.py (new), standalone entry point, not wired into main.py
- tests/test_forward.py (new)
- outputs/forward/ (gitignored)

Must not edit any existing file.

Tasks:
1. Fetch upcoming 2026-27 fixtures from a fresh source, never the data/ cache.
2. Import the Stage 2 filter from stage2_dynamic.py. Use the same home_adv
   value main.py uses, fixed from the original training split. Do not
   recompute it.
3. For each upcoming fixture not already logged, append a row to
   outputs/forward/predictions.csv: fixture id, kickoff (UTC), logged_at (UTC),
   pred_home_win, pred_draw, pred_away_win, lambda_home, mu_away.
   Append only. Never overwrite. Skip fixtures already logged.
4. Refuse to log any fixture whose kickoff has passed.
5. python forward_logger.py --score: fill in actual results for finished
   matches and print RPS and LogLoss on logged rows.

Done when: running python forward_logger.py twice produces no duplicate rows,
and --score runs.

## Merge order
1. forward-logger (touches no shared files)
2. gate-b-lineup (may touch main.py)
