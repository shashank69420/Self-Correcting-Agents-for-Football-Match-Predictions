# Goal markets: calibration

**DESCRIPTIVE: recomputed forecasts, not timestamped before kickoff; no test, no claim.**

Parameters were fixed before 2026-27 data was fetched. Forecasts were recomputed after the matches were played and are not timestamped before kickoff.

Model: frozen P2 goals-only (`results/p2/candidate_p2.json`, sha256 bf7d5226316fe2cb4473e7120c624802f7dcdbd651b603200747f179728b0e3f); code commit e77654183102fa151e9d4f1c0448287bfe9687b1 (fan_features.py sha256 650210e5c0e0a430..., differs from that commit: True).

Forecasts: one run of the filter over the 19,716 concatenated rows; a row's forecast uses only earlier rows. Markets come from the rho-corrected 30-goal score grid. Nothing was tuned or recalibrated. Half-widths are 95% normal approximations. No TEST_INDEX row is scored.

Climatology baseline: 2,256 H rows dated before 2020-07-01 (last 2020-06-30 21:30:00); over 2.5 rate 0.5346, BTTS rate 0.5399.

## Live 2026-27 test set

| market | n | brier | brier_clim | skill | brier_diff | log_loss | log_loss_clim | log_loss_diff | mean_pred | observed |
|---|---|---|---|---|---|---|---|---|---|---|
| Over 2.5 | 563 | 0.2285 | 0.2428 | 0.0589 | -0.0143 +/- 0.0088 | 0.6487 | 0.6787 | -0.0300 +/- 0.0188 | 0.5604 +/- 0.0093 | 0.6217 +/- 0.0401 |
| BTTS | 563 | 0.2407 | 0.2450 | 0.0177 | -0.0043 +/- 0.0068 | 0.6742 | 0.6831 | -0.0090 +/- 0.0141 | 0.5544 +/- 0.0069 | 0.5826 +/- 0.0407 |

brier_diff and log_loss_diff: model minus climatology, mean per match +/- 95% half-width.

Reliability, Over 2.5 (10 equal-width bins):

| bin | n | mean_predicted | observed | observed_hw95 |
|---|---|---|---|---|
| [0.0, 0.1) | 0 | n/a | n/a | n/a |
| [0.1, 0.2) | 0 | n/a | n/a | n/a |
| [0.2, 0.3) | 5 | 0.2750 | 0.2000 | 0.3506 |
| [0.3, 0.4) | 41 | 0.3563 | 0.4390 | 0.1519 |
| [0.4, 0.5) | 122 | 0.4552 | 0.5492 | 0.0883 |
| [0.5, 0.6) | 186 | 0.5537 | 0.6129 | 0.0700 |
| [0.6, 0.7) | 154 | 0.6467 | 0.7013 | 0.0723 |
| [0.7, 0.8) | 44 | 0.7321 | 0.7500 | 0.1279 |
| [0.8, 0.9) | 11 | 0.8348 | 0.8182 | 0.2279 |
| [0.9, 1.0] | 0 | n/a | n/a | n/a |

Reliability, BTTS (10 equal-width bins):

| bin | n | mean_predicted | observed | observed_hw95 |
|---|---|---|---|---|
| [0.0, 0.1) | 0 | n/a | n/a | n/a |
| [0.1, 0.2) | 0 | n/a | n/a | n/a |
| [0.2, 0.3) | 0 | n/a | n/a | n/a |
| [0.3, 0.4) | 24 | 0.3721 | 0.3333 | 0.1886 |
| [0.4, 0.5) | 120 | 0.4602 | 0.5333 | 0.0893 |
| [0.5, 0.6) | 248 | 0.5522 | 0.5927 | 0.0611 |
| [0.6, 0.7) | 150 | 0.6390 | 0.6200 | 0.0777 |
| [0.7, 0.8) | 21 | 0.7233 | 0.7619 | 0.1822 |
| [0.8, 0.9) | 0 | n/a | n/a | n/a |
| [0.9, 1.0] | 0 | n/a | n/a | n/a |

Scorelines (n 563):

| scoreline | hit_rate | mean_predicted |
|---|---|---|
| top1 | 0.0959 +/- 0.0243 | 0.1162 +/- 0.0016 |
| top3 | 0.2718 +/- 0.0367 | 0.3085 +/- 0.0040 |

top1: the most likely scoreline; top3: the three most likely. mean_predicted is the mean model probability of those same scorelines.

## VAL (H, 2023-07-01 onward, excluding TEST_INDEX)

| market | n | brier | brier_clim | skill | brier_diff | log_loss | log_loss_clim | log_loss_diff | mean_pred | observed |
|---|---|---|---|---|---|---|---|---|---|---|
| Over 2.5 | 4291 | 0.2410 | 0.2476 | 0.0268 | -0.0066 +/- 0.0033 | 0.6750 | 0.6884 | -0.0134 +/- 0.0070 | 0.5413 +/- 0.0034 | 0.5516 +/- 0.0149 |
| BTTS | 4291 | 0.2468 | 0.2472 | 0.0017 | -0.0004 +/- 0.0024 | 0.6868 | 0.6876 | -0.0009 +/- 0.0049 | 0.5348 +/- 0.0024 | 0.5544 +/- 0.0149 |

brier_diff and log_loss_diff: model minus climatology, mean per match +/- 95% half-width.

Reliability, Over 2.5 (10 equal-width bins):

| bin | n | mean_predicted | observed | observed_hw95 |
|---|---|---|---|---|
| [0.0, 0.1) | 0 | n/a | n/a | n/a |
| [0.1, 0.2) | 0 | n/a | n/a | n/a |
| [0.2, 0.3) | 39 | 0.2691 | 0.3333 | 0.1479 |
| [0.3, 0.4) | 457 | 0.3627 | 0.4486 | 0.0456 |
| [0.4, 0.5) | 1076 | 0.4535 | 0.4730 | 0.0298 |
| [0.5, 0.6) | 1377 | 0.5485 | 0.5614 | 0.0262 |
| [0.6, 0.7) | 968 | 0.6434 | 0.6147 | 0.0307 |
| [0.7, 0.8) | 330 | 0.7393 | 0.7182 | 0.0485 |
| [0.8, 0.9) | 41 | 0.8252 | 0.8049 | 0.1213 |
| [0.9, 1.0] | 3 | 0.9108 | 0.6667 | 0.5334 |

Reliability, BTTS (10 equal-width bins):

| bin | n | mean_predicted | observed | observed_hw95 |
|---|---|---|---|---|
| [0.0, 0.1) | 0 | n/a | n/a | n/a |
| [0.1, 0.2) | 0 | n/a | n/a | n/a |
| [0.2, 0.3) | 1 | 0.2865 | 0.0000 | 0.0000 |
| [0.3, 0.4) | 204 | 0.3757 | 0.4853 | 0.0686 |
| [0.4, 0.5) | 1297 | 0.4598 | 0.5166 | 0.0272 |
| [0.5, 0.6) | 1865 | 0.5497 | 0.5512 | 0.0226 |
| [0.6, 0.7) | 844 | 0.6380 | 0.6268 | 0.0326 |
| [0.7, 0.8) | 80 | 0.7242 | 0.6625 | 0.1036 |
| [0.8, 0.9) | 0 | n/a | n/a | n/a |
| [0.9, 1.0] | 0 | n/a | n/a | n/a |

Scorelines (n 4,291):

| scoreline | hit_rate | mean_predicted |
|---|---|---|
| top1 | 0.1326 +/- 0.0101 | 0.1198 +/- 0.0006 |
| top3 | 0.3279 +/- 0.0140 | 0.3185 +/- 0.0014 |

top1: the most likely scoreline; top3: the three most likely. mean_predicted is the mean model probability of those same scorelines.

## Grid diagnostic

Maximum absolute difference between 1X2 from the corrected 30-goal grid and the model's own max_goals 10 forecast. A description, not a failure.

- live: n 563, max 3.528e-04, rows above 0.01: 0
- val: n 4,291, max 5.796e-04, rows above 0.01: 0
