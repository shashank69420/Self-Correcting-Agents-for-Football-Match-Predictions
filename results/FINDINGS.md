# B12 findings

Every number below is checked by `tools/verify_claims.py` against `results/claims.json`: each number maps to a
repository file and a pattern that must match next to it. Where no file records a number it says "not recorded".
Sources are tracked files: `results/sources/` (the Stage 1-5 notebook output and the Transfermarkt README),
`results/audit/` (the Gate A audit run), `results/experiments/`, `DECISIONS.md` and `CLAUDE.md`.

## 1. Data and pipeline
- 56 league-seasons: 8 leagues (ENG, ESP, DEU, ITA, FRA, NLD, PRT, TUR) x 7 seasons (2019-20 to 2025-26), 19,145 valid
  matches.
- 80% / 20% chronological split: training 15,316 matches, 2019-08-02 to 2025-02-01; test 3,829 matches,
  2025-02-01 to 2026-05-24. One training match shares the first test kickoff, so TEST is always selected by row
  identity, never by date.
- Transfermarkt matching (`python main.py --audit`, `results/audit/gate_a_audit.txt`): strictly matched 19,140 of
  19,145 fixtures. Data files unchanged by the audit (sha256 before and after identical).
- Gate A, test period: 3,829 fixtures, 3,829 matched (100.00%), both sides 11 starters 3,826 (99.92%), against the
  90% threshold. GATE A: PASSED.

## 2. Baselines (3,545 common test rows; Stage 1 skips 284 test matches with unseen teams)

| Model | RPS | Brier | Log-loss |
|---|---|---|---|
| Stage 1 (static Dixon-Coles) | 0.2057245 | 0.1994488 | 1.0022933 |
| Stage 2 (sequential filter) | 0.2060203 | 0.1998337 | 1.0056991 |
| Closing market average, same 3,545 rows | 0.1926041 | 0.1898924 | 0.9598217 |

Stage 2 RPS on all 3,829 held-out matches: 0.2059. The Stage 2 minus market RPS gap is 0.0134162 (derived from the two
RPS values above). The market uses later information than the T-60 forecasts, so it is a benchmark only.

## 3. Surprise mechanism (Stages 3 to 5), all retrospective on the inspected test window
- **Stage 3, persistent change detector (one ordinary Poisson update; evidence only raises future process noise).**
  Validation (three chronological folds on training data) selected CHANGE_SCALE 0 (log-loss 0.9979680 at 0; every
  larger scale was not eligible), so the detector never added variance: 0 of 3,829 test matches had extra variance, and
  Stage 3 equals Stage 2 on every metric (Stage 3 minus Stage 2 RPS 0.0). Cause: validation found no gain.
- **Stage 4, surprise multiplier on the mean step (SUPERSEDED, confirmed sign-inverted: higher surprise gave a smaller
  correction).** Validation selected sensitivity 0.25; log-loss difference -0.0010106, 95% CI [-0.0025560, 0.0001155],
  which includes zero. Test, 3,545 rows: RPS 0.2058885 and log-loss 1.0054757 against Stage 2's 0.2060203 and
  1.0056991. Descriptive only. Cause: the update direction was inverted, so no reliable effect.
- **Stage 5, corrected direction (surprise scales the mean step).** Validation selected sensitivity 0 (log-loss
  0.9979680 at 0 against 1.0066392 at 0.25, 1.0092615 at 0.5 and 1.0136471 at 1), so surprise scaling was inactive and
  all forecasts equal Stage 2 (multiplier mean, min and max all 1.0000000). Cause: every positive sensitivity made
  validation log-loss worse.

## 4. Lineup Gate B: FAILED (2026-10-19)
- c_att +0.0950, CI [0.0487, 0.1413]; c_def -0.0022, CI [-0.0413, 0.0368]. Final for the locked spec. The gate's
  pass criterion is not restated in the files; the c_def interval includes 0.
- Diagnosis (read-only `/diagnose`): class (c) true null for the defence term, with (d) weak defence-line proxy as
  secondary. Independent GLM and feature recomputation reproduced the fit; 0/200 within-season placebos passed the
  gate; minimum detectable c_def 0.056, power 99.8% for an attack-sized effect.
- Exploratory attack-only run (post-hoc, chosen after Gate B failed, from training data only; the single approved
  post-hoc spec): frozen c_att +0.09503, defence deltas 0, coverage 3786/3829 (98.88%). Log-loss difference
  +0.000109 (slightly worse), 95% CI [-0.000669, +0.000878] on 3543 covered common rows: no improvement, not
  significant. Placebo +0.000148, CI [-0.000677, +0.001007].

## 5. P1 (learned parameters): selection-period, not out-of-sample
P1 = E1 + E3 + E5 on top of Stage 2: process_noise 0.005, initial_var 0.3, cold_defence 0.3 for teams first seen
after their league's first season, rate clip [0.15, 6.0] on, Dixon-Coles rho -0.04. E2 (drift), E4 (league effects)
and E6 (recalibration) were rejected; calibration is null. Selection used DEV (8,769 rows) and VAL (4,291 rows) only.

| Exp | Chosen | Log-loss change [99% CI] | Holm p | Verdict |
|---|---|---|---|---|
| E1 | q 0.005, initial var 0.3 | -0.015803 [-0.020189, -0.012334] | 0.002999 | ACCEPTED |
| E2 | none (no drift) | 0.000000 | 1.000000 | REJECTED |
| E3 | cold_defence 0.3, clip on | -0.000768 [-0.001715, -0.000099] | 0.005997 | ACCEPTED |
| E4 | none (league effects off) | 0.000000 | 1.000000 | REJECTED |
| E5 | rho -0.04 | -0.000552 [-0.000999, -0.000116] | 0.002999 | ACCEPTED |
| E6 | T 1.255 plus class bias | -0.002784 [-0.006639, +0.001068] (VAL only) | 0.074963 | REJECTED |

Selection-period, not out-of-sample (VAL took part in selection).

| Split (selection-period, not out-of-sample) | Model | RPS | Brier | Log-loss | Accuracy |
|---|---|---|---|---|---|
| DEV (8,769) | Stage 2 | 0.20813 | 0.20074 | 1.01150 | 0.51614 |
| DEV (8,769) | P1 | 0.20433 | 0.19785 | 0.99709 | 0.52264 |
| VAL (4,291) | Stage 2 | 0.20083 | 0.19783 | 1.00384 | 0.51783 |
| VAL (4,291) | P1 | 0.19665 | 0.19458 | 0.98117 | 0.52598 |

Share of the Stage 2 to closing-market gap closed by P1 on rows with closing odds: RPS 29.29% (DEV, 8,740 rows),
27.68% (VAL, 4,291 rows). VAL log-loss gap closed is 37.83%, but 11 VAL rows with a baseline rate outside
[0.15, 6.0] carry 36% of the VAL log-loss gain (9 DEV rows: 1%); on all other rows P1 still improves (VAL
0.994245 to 0.979695).

## 6. One-shot TEST result: retrospective holdout: examined in Stages 1-5 and P1 selection
P1's parameters were selected on DEV/VAL only; this is the first scoring of P1 on TEST_INDEX.
Pre-registered rule: P1 is a TEST improvement only if the 95% paired week-block CI (2000 resamples, seed 20261026)
upper bound on the mean log-loss difference (P1 minus Stage 2) over all 3,829 TEST rows is below 0.

- **Primary:** log-loss 1.008321 (Stage 2) to 0.995493 (P1); difference **-0.012828**, 95% CI
  **[-0.015519, -0.010091]**. Upper bound below 0: **ACCEPTED** as a TEST improvement.
- **Secondary, descriptive.** All 3,829 rows: RPS 0.205946 to 0.202357, Brier 0.200442 to 0.197737, accuracy
  0.516584 to 0.521285. Common 3,545 rows: RPS 0.206020 to 0.202578, Brier 0.199834 to 0.197250, log-loss
  1.005699 to 0.993635 (difference -0.012065, CI [-0.014553, -0.009332]), accuracy 0.518759 to 0.524118.
  Closing-odds TEST rows (3,829 of 3,829): market RPS 0.192423; P1 closes 26.54% of the RPS gap (Brier 26.85%,
  log-loss 27.47%).
- **Descriptive split, post-scoring, not a test:** 1 of 3,829 rows (and 1 of 3,545 common rows) has a baseline
  rate outside [0.15, 6.0]; it contributes -0.02% of the total gain (log-loss 0.027037 to 0.035196). The 3,828
  normal rows carry the gain: 1.008578 to 0.995744 (3,544 common rows: 1.005975 to 0.993905).

## 7. Limitations
- Market odds are a benchmark only (closing odds are later than T-60). Non-closing odds are described by
  football-data.co.uk/notes.txt as: "Betting odds for weekend games are collected Friday afternoons, and on Tuesday
  afternoons for midweek games." That is a schedule, not a per-match timestamp, so the snapshot-odds timing is
  schedule-level only.
- Transfermarkt data is a frozen upstream snapshot: its README states "Updates are paused. The dataset is current to
  6 July 2026." (`results/sources/transfermarkt_readme.txt`, read 2026-10-25). The date the local `data/*.gz` files
  were downloaded is not recorded.
- The test window is not fresh: it was examined during Stages 1-5, and P1 was then scored on it once. All TEST
  results are retrospective.
- One post-hoc lineup run (attack-only, Gate B stays FAILED).
- The `--lineup` path is verified only by tests and the end-to-end check.
- `home_adv` is Stage 2's fixed value from the whole training window, so DEV and VAL forecasts carry slight
  look-ahead within the training window; DEV and VAL are selection-period numbers.
- The TEST scoring scripts are in the repository: `results/experiments/test_once.py` and `split_test.py`, with
  `test_once_README.md`. A reproduction run (`results/experiments/test_once_repro.txt`) gave log-loss difference
  -0.012828 and CI [-0.015519, -0.010091], matching the original. A rerun is a reproduction, not a new test.

## 8. Forward test
Not started. `outputs/forward/` does not exist, and the `forward-logger` branch has no `forward_logger.py`.
