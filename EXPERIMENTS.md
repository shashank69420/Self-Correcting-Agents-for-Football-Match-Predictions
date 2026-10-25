# Stage 2 experiments (branch experiments)

Greedy, fixed-order experiments E1-E6 on the Stage 2 filter (`exp_model.run_filter`), each on top of the
current incumbent. Code: `exp_model.py`, `exp_harness.py`, `run_experiments.py`; tests: `tests/test_exp.py`.

## Protocol (locked before any run)
- Splits by row identity: TEST = `test_df.index` from `chronological_split` (never scored here).
  BURN-IN = before 2020-07-01 (2,256 rows, filtered, never scored). DEV = 2020-07-01 to 2023-06-30
  (8,769 rows). VAL = from 2023-07-01, excluding TEST_INDEX (4,291 rows, to 2025-02-01).
- Selection: lowest DEV mean log-loss in the grid. Accept only if (i) DEV log-loss improves on the incumbent,
  (ii) VAL log-loss improves, and (iii) the 99% paired week-block bootstrap CI (2000 resamples, seed 20261025)
  for candidate minus incumbent log-loss on DEV+VAL has upper bound < 0 (E6: VAL only). One pass per grid.
- Default params reproduce Stage 2 bit-exactly on all 19,145 rows (`run_experiments.py --check`: max abs
  difference 0 for probabilities, rates and all export columns; non-TEST forecasts are identical with or
  without the TEST rows present).

## Caveats
- `home_adv` is Stage 2's fixed value from the full training window (to 2025-02-01), so DEV and VAL forecasts
  carry slight look-ahead inside the training window. Baseline and candidates share it; TEST is not involved.
- VAL takes part in selection (rules ii and iii), so DEV and VAL results are selection-period, retrospective
  numbers, not out-of-sample estimates.
- E2's "new season" rule (gap > 45 days) also fires at the 2022 World Cup break in some leagues.
- E5 uses the Dixon-Coles sign convention: rho < 0 inflates 0-0 and 1-1. Factors are floored at 0, then the
  grid is renormalised.
- E6: rule (i) holds by construction (fitted on DEV); the binding checks are (ii) and (iii) on VAL.

## Results
