# One-shot TEST scoring of frozen P1

**TEST, one-shot, retrospective (this window was examined during Stages 1-5 and P1 selection)**

Pre-registered rule (fixed before running): primary = 95% paired week-block bootstrap CI (2000 resamples, seed 20261026) on mean log-loss difference, P1 minus Stage 2 baseline, over all 3829 TEST_INDEX rows. P1 is accepted as a TEST improvement only if the CI upper bound is below 0. Everything else is secondary and descriptive.

## 1. Parameters

```json
{
  "candidate": "P1",
  "accepted_experiments": [
    "E1",
    "E3",
    "E5"
  ],
  "params": {
    "process_noise": 0.005,
    "initial_var": 0.3,
    "cold_defence": 0.3,
    "clip_rates": true,
    "rho": -0.04
  },
  "calibration": null,
  "note": "Overrides of exp_model.DEFAULT_PARAMS; home_adv stays compute_home_adv(train_df, test_df)."
}
```

Confirmed equal to the accepted set: True. Accepted experiments ['E1', 'E3', 'E5']; verdicts {'E1': 'ACCEPTED', 'E2': 'REJECTED', 'E3': 'ACCEPTED', 'E4': 'REJECTED', 'E5': 'ACCEPTED', 'E6': 'REJECTED'}; calibration None. home_adv is the fixed Stage 2 value. Baseline = `exp_model.run_filter` defaults, max abs probability difference to `run_sequential_filter` over all 19,145 rows: 0.0e+00.

## 2. Primary result

- Rows: 3829 (selected by TEST_INDEX only)
- Mean log-loss difference, P1 minus baseline: -0.012828 (baseline 1.008321, P1 0.995493)
- 95% paired week-block CI: [-0.015519, -0.010091]
- **Verdict: ACCEPTED as a TEST improvement.**

## 3. Secondary metrics (descriptive only)

TEST, one-shot, retrospective (this window was examined during Stages 1-5 and P1 selection).

### All TEST rows

| model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|
| Baseline | 3829 | 0.205946 | 0.200442 | 1.008321 | 0.516584 |
| P1 | 3829 | 0.202357 | 0.197737 | 0.995493 | 0.521285 |

### Common rows (teams seen in training; main.py comparison set)

| model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|
| Baseline | 3545 | 0.206020 | 0.199834 | 1.005699 | 0.518759 |
| P1 | 3545 | 0.202578 | 0.197250 | 0.993635 | 0.524118 |

- All TEST rows (n=3829): log-loss P1 minus baseline -0.012828, 95% week-block CI [-0.015519, -0.010091] (descriptive)
- Common rows (n=3545): log-loss P1 minus baseline -0.012065, 95% week-block CI [-0.014553, -0.009332] (descriptive)

### Closing-odds TEST rows (3829 of 3829)

| model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|
| Closing market | 3829 | 0.192423 | 0.190366 | 0.961623 | 0.544790 |
| Baseline | 3829 | 0.205946 | 0.200442 | 1.008321 | 0.516584 |
| P1 | 3829 | 0.202357 | 0.197737 | 0.995493 | 0.521285 |

Gap closed by P1 = (baseline - P1) / (baseline - market):

| metric | baseline | P1 | market | gap closed |
|---|---|---|---|---|
| RPS | 0.205946 | 0.202357 | 0.192423 | 26.54% |
| Brier | 0.200442 | 0.197737 | 0.190366 | 26.85% |
| LogLoss | 1.008321 | 0.995493 | 0.961623 | 27.47% |

## Notes
- The baseline's 3545 common-row RPS (0.206020) matches the main.py anchor (0.2060). No error occurred and nothing was re-run.
- P1's parameters were selected on DEV/VAL only; this is the first scoring of P1 on TEST_INDEX. The Stage 2 baseline on this window was already reported by main.py.
- The script (`test_once.py`, `primary` then `secondary`) lives in the session scratchpad, not the repo (outside the ownership list). `exp_harness.scored/summary` refuse TEST rows by design, so it used `row_scores`, `market_probs`, `week_block_ci` and `metrics.probability_metrics` directly.

## DESCRIPTIVE SPLIT, post-scoring, not a test

TEST, one-shot, retrospective. A split of the already-scored rows above; no new comparison, no CI, no decision. Outside = baseline lambda_home or mu_away outside [0.15, 6.0] (same rows for both models); other = the rest.

### All 3829 TEST rows

| group | n | baseline log-loss | P1 log-loss | summed gain (baseline - P1) |
|---|---|---|---|---|
| outside | 1 | 0.027037 | 0.035196 | -0.008159 |
| other | 3828 | 1.008578 | 0.995744 | 49.128279 |
| total | 3829 | 1.008321 | 0.995493 | 49.120120 |

Share of the total log-loss gain from outside rows: -0.02% (1 of 3829 rows).

### 3545 common rows

| group | n | baseline log-loss | P1 log-loss | summed gain (baseline - P1) |
|---|---|---|---|---|
| outside | 1 | 0.027037 | 0.035196 | -0.008159 |
| other | 3544 | 1.005975 | 0.993905 | 42.777146 |
| total | 3545 | 1.005699 | 0.993635 | 42.768987 |

Share of the total log-loss gain from outside rows: -0.02% (1 of 3545 rows).

