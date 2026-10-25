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

## E1: Hyperparameters -- ACCEPTED

Incumbent: `{}` (empty = Stage 2 defaults). Grid run time 11.0 s. All numbers are selection-period, retrospective, not out-of-sample.

| process_noise | initial_var | dev_logloss | val_logloss | dev_rps | val_rps |
|---|---|---|---|---|---|
| 0.005000 | 0.300000 | 0.997962 | 0.983396 | 0.204573 | 0.196935 |
| 0.005000 | 0.600000 | 0.999243 | 0.986803 | 0.204939 | 0.197339 |
| 0.005000 | 1.000000 | 1.000483 | 0.992369 | 0.205266 | 0.197768 |
| 0.010000 | 0.300000 | 1.008931 | 0.994014 | 0.207452 | 0.199999 |
| 0.010000 | 0.600000 | 1.010204 | 0.997775 | 0.207802 | 0.200421 |
| 0.010000 | 1.000000 | 1.011496 | 1.003838 | 0.208130 | 0.200834 |
| 0.020000 | 0.300000 | 1.027216 | 1.011120 | 0.212074 | 0.204741 |
| 0.020000 | 0.600000 | 1.028495 | 1.015156 | 0.212407 | 0.205160 |
| 0.020000 | 1.000000 | 1.029875 | 1.021374 | 0.212732 | 0.205548 |
| 0.040000 | 0.300000 | 1.057331 | 1.039295 | 0.219148 | 0.211767 |
| 0.040000 | 0.600000 | 1.058634 | 1.043566 | 0.219456 | 0.212152 |
| 0.040000 | 1.000000 | 1.060129 | 1.049654 | 0.219763 | 0.212500 |

Chosen (lowest DEV log-loss): `{"process_noise": 0.005, "initial_var": 0.3}`

| | DEV log-loss (n=8769) | VAL log-loss (n=4291) |
|---|---|---|
| incumbent | 1.011496 | 1.003838 |
| chosen | 0.997962 | 0.983396 |

Chosen minus incumbent log-loss on DEV+VAL (n=13060): -0.015803; 99% paired week-block CI [-0.020189, -0.012334] (2000 resamples, seed 20261025); one-sided bootstrap p = 0.0005.

- (i) DEV log-loss improves: yes
- (ii) VAL log-loss improves: yes
- (iii) 99% CI upper bound < 0: yes

Verdict: **ACCEPTED**.
Deviation: the first E1 invocation crashed before writing any output (results/experiments/ did not
exist yet); no result was written or seen. Fixed with os.makedirs and re-ran the identical grid once.
Note: the chosen point is at the grid corner (lowest q, lowest initial variance); the grid is locked and
was not extended.

## E2: Drift -- REJECTED

Incumbent: `{"process_noise": 0.005, "initial_var": 0.3}` (empty = Stage 2 defaults). Grid run time 12.4 s. All numbers are selection-period, retrospective, not out-of-sample.

| drift_per_day | season_var | dev_logloss | val_logloss | dev_rps | val_rps |
|---|---|---|---|---|---|
| 0.000000 | 0.000000 | 0.997962 | 0.983396 | 0.204573 | 0.196935 |
| 0.000000 | 0.020000 | 0.999973 | 0.984171 | 0.205075 | 0.197164 |
| 0.000000 | 0.050000 | 1.002960 | 0.985650 | 0.205823 | 0.197598 |
| 0.000200 | 0.000000 | 1.001701 | 0.987135 | 0.205555 | 0.198015 |
| 0.000200 | 0.020000 | 1.003595 | 0.987875 | 0.206024 | 0.198242 |
| 0.000200 | 0.050000 | 1.006380 | 0.989230 | 0.206711 | 0.198645 |
| 0.000500 | 0.000000 | 1.006949 | 0.992289 | 0.206922 | 0.199505 |
| 0.000500 | 0.020000 | 1.008689 | 0.992991 | 0.207345 | 0.199723 |
| 0.000500 | 0.050000 | 1.011234 | 0.994226 | 0.207958 | 0.200092 |

Chosen (lowest DEV log-loss): `{"drift_per_day": 0.0, "season_var": 0.0}`

| | DEV log-loss (n=8769) | VAL log-loss (n=4291) |
|---|---|---|
| incumbent | 0.997962 | 0.983396 |
| chosen | 0.997962 | 0.983396 |

Chosen minus incumbent log-loss on DEV+VAL (n=13060): +0.000000; 99% paired week-block CI [+0.000000, +0.000000] (2000 resamples, seed 20261025); one-sided bootstrap p = 1.0000.

- (i) DEV log-loss improves: NO
- (ii) VAL log-loss improves: NO
- (iii) 99% CI upper bound < 0: NO

Verdict: **REJECTED**.

## E3: Cold start and rate clip -- ACCEPTED

Incumbent: `{"process_noise": 0.005, "initial_var": 0.3}` (empty = Stage 2 defaults). Grid run time 20.3 s. All numbers are selection-period, retrospective, not out-of-sample.

| cold_attack | cold_defence | clip_rates | dev_logloss | val_logloss | dev_rps | val_rps |
|---|---|---|---|---|---|---|
| 0.000000 | 0.000000 | False | 0.997962 | 0.983396 | 0.204573 | 0.196935 |
| 0.000000 | 0.000000 | True | 0.997959 | 0.982923 | 0.204572 | 0.196958 |
| 0.000000 | 0.150000 | False | 0.997554 | 0.983218 | 0.204451 | 0.196823 |
| 0.000000 | 0.150000 | True | 0.997551 | 0.982635 | 0.204450 | 0.196852 |
| 0.000000 | 0.300000 | False | 0.997292 | 0.983123 | 0.204371 | 0.196733 |
| 0.000000 | 0.300000 | True | 0.997289 | 0.982435 | 0.204370 | 0.196767 |
| 0.150000 | 0.000000 | False | 0.997840 | 0.983188 | 0.204506 | 0.196853 |
| 0.150000 | 0.000000 | True | 0.997837 | 0.982719 | 0.204506 | 0.196877 |
| 0.150000 | 0.150000 | False | 0.997548 | 0.983084 | 0.204424 | 0.196764 |
| 0.150000 | 0.150000 | True | 0.997545 | 0.982504 | 0.204423 | 0.196793 |
| 0.150000 | 0.300000 | False | 0.997406 | 0.983067 | 0.204383 | 0.196696 |
| 0.150000 | 0.300000 | True | 0.997403 | 0.982380 | 0.204383 | 0.196731 |
| 0.300000 | 0.000000 | False | 0.997867 | 0.983080 | 0.204485 | 0.196800 |
| 0.300000 | 0.000000 | True | 0.997864 | 0.982616 | 0.204484 | 0.196824 |
| 0.300000 | 0.150000 | False | 0.997682 | 0.983048 | 0.204438 | 0.196732 |
| 0.300000 | 0.150000 | True | 0.997680 | 0.982471 | 0.204437 | 0.196762 |
| 0.300000 | 0.300000 | False | 0.997653 | 0.983103 | 0.204434 | 0.196685 |
| 0.300000 | 0.300000 | True | 0.997651 | 0.982417 | 0.204433 | 0.196720 |

Chosen (lowest DEV log-loss): `{"cold_attack": 0.0, "cold_defence": 0.3, "clip_rates": true}`

| | DEV log-loss (n=8769) | VAL log-loss (n=4291) |
|---|---|---|
| incumbent | 0.997962 | 0.983396 |
| chosen | 0.997289 | 0.982435 |

Chosen minus incumbent log-loss on DEV+VAL (n=13060): -0.000768; 99% paired week-block CI [-0.001715, -0.000099] (2000 resamples, seed 20261025); one-sided bootstrap p = 0.0015.

- (i) DEV log-loss improves: yes
- (ii) VAL log-loss improves: yes
- (iii) 99% CI upper bound < 0: yes

Verdict: **ACCEPTED**.
