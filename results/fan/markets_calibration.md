# Goal markets: calibration

**DESCRIPTIVE: recomputed forecasts, not timestamped before kickoff; no test, no claim.**

Parameters were fixed before 2026-27 data was fetched. Forecasts were recomputed after the matches were played and are not timestamped before kickoff.

Model: frozen P2 goals-only (`results/p2/candidate_p2.json`, sha256 bf7d5226316fe2cb4473e7120c624802f7dcdbd651b603200747f179728b0e3f); code commit e77654183102fa151e9d4f1c0448287bfe9687b1 (fan_features.py sha256 650210e5c0e0a430..., differs from that commit: True).

Forecasts: one run of the filter over the concatenated history and the 2026-27 snapshot; a row's forecast uses only earlier rows. Markets come from the rho-corrected market score grid. Nothing was tuned or recalibrated. No TEST_INDEX row is scored. Half-widths are normal approximations at the usual two-sided level.

The over market is over 2.5 goals in total; BTTS is both teams to score. The climatology baseline is the base rate over history rows dated before the DEV start, so it never sees a scored row.

Numbers are not repeated here. They are in `markets_calibration.json`: `calibration.live` and `calibration.val` (Brier and log-loss against climatology, Brier skill, mean predicted against observed rate, a reliability table with counts, scoreline hit rates), `climatology`, and `grid_diagnostic`.

## Live 2026-27 test set

- Over 2.5: the Brier score is better than climatology and the difference is outside its interval. The mean predicted rate is below the observed rate, and the gap is outside the interval of the observed rate.
- BTTS: the Brier score is better than climatology and the difference is inside its interval. The mean predicted rate is below the observed rate, and the gap is inside the interval of the observed rate.
- The hit rate of the most likely scoreline is below its mean predicted probability, and the gap is inside the interval of the hit rate.
- The hit rate of the three most likely scorelines is below its mean predicted probability, and the gap is outside the interval of the hit rate.

## VAL (history rows from the VAL start date onward, excluding TEST_INDEX)

- Over 2.5: the Brier score is better than climatology and the difference is outside its interval. The mean predicted rate is below the observed rate, and the gap is inside the interval of the observed rate.
- BTTS: the Brier score is better than climatology and the difference is inside its interval. The mean predicted rate is below the observed rate, and the gap is outside the interval of the observed rate.
- The hit rate of the most likely scoreline is above its mean predicted probability, and the gap is outside the interval of the hit rate.
- The hit rate of the three most likely scorelines is above its mean predicted probability, and the gap is inside the interval of the hit rate.

## Grid diagnostic

The market grid and the model's own smaller grid give the same 1X2 to within a small difference. The largest difference per set is in `grid_diagnostic`. This is a description, not a failure.

- live: no row exceeds the flag threshold.
- val: no row exceeds the flag threshold.
