# P2 frozen candidates on TEST rows: DESCRIPTIVE: TEST is not fresh; no claim from this

**DESCRIPTIVE: TEST is not fresh; no claim from this.** TEST_INDEX (3829 rows) was examined in Stages 1-5 and in the P1 test; this look comes after the fresh scoring (`results/p2/fresh_once.md`) and changes nothing. Helpers: `exp_harness.row_scores`/`market_probs`, `metrics.probability_metrics`. Stack and market-only use the frozen DEV+VAL coefficients (descriptive Phase 6 only).

## All TEST rows (n=3829). DESCRIPTIVE: TEST is not fresh; no claim from this

| model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|
| Stage 2 baseline | 3829 | 0.205946 | 0.200442 | 1.008321 | 0.516584 |
| P1 | 3829 | 0.202357 | 0.197737 | 0.995493 | 0.521285 |
| Goals-only candidate | 3829 | 0.197794 | 0.194469 | 0.980044 | 0.530687 |

## TEST rows with snapshot odds (n=3829). DESCRIPTIVE: TEST is not fresh; no claim from this

| model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|
| Stage 2 baseline | 3829 | 0.205946 | 0.200442 | 1.008321 | 0.516584 |
| P1 | 3829 | 0.202357 | 0.197737 | 0.995493 | 0.521285 |
| Goals-only candidate | 3829 | 0.197794 | 0.194469 | 0.980044 | 0.530687 |
| Stack | 3829 | 0.192520 | 0.190384 | 0.961080 | 0.541133 |
| Market-only (snapshot) | 3829 | 0.192605 | 0.190467 | 0.961423 | 0.540872 |

## TEST rows with snapshot and closing odds (n=3829). DESCRIPTIVE: TEST is not fresh; no claim from this

| model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|
| Stage 2 baseline | 3829 | 0.205946 | 0.200442 | 1.008321 | 0.516584 |
| P1 | 3829 | 0.202357 | 0.197737 | 0.995493 | 0.521285 |
| Goals-only candidate | 3829 | 0.197794 | 0.194469 | 0.980044 | 0.530687 |
| Stack | 3829 | 0.192520 | 0.190384 | 0.961080 | 0.541133 |
| Market-only (snapshot) | 3829 | 0.192605 | 0.190467 | 0.961423 | 0.540872 |
| Closing market (average) | 3829 | 0.192423 | 0.190366 | 0.961623 | 0.544790 |
