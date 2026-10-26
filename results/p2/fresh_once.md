# FRESH out-of-time (2015-16 to 2018-19), first scoring

**FRESH out-of-time (2015-16 to 2018-19), first scoring.** Pre-registered in `p2/PREREGISTRATION.md`; candidates frozen in `results/p2/candidate_p2.json` (sha256 bf7d5226316fe2cb4473e7120c624802f7dcdbd651b603200747f179728b0e3f). Rows: every F match of 2015-2016 to 2018-2019 (n=10976); 2014-2015 is burn-in. home_adv 0.203562 (main-data value). CIs: paired week-block bootstrap, 2000 resamples, seed 20261030, level 1 - 0.05/3 (98.3%). A test passes only if the upper bound is below 0.

Check (forecasts only): p2_model with shots_w = 0 vs exp_model P1 on all 13720 F rows, max abs probability difference 0.0e+00.

## Primary tests

| test | comparison | n | first | second | mean diff | 98.3% CI | verdict |
|---|---|---|---|---|---|---|---|
| T-A | P1 minus Stage 2 baseline | 10976 | 0.983514 | 0.997499 | -0.013985 | [-0.016001, -0.012097] | **PASS** |
| T-B | Goals-only candidate minus P1 | 10976 | 0.969656 | 0.983514 | -0.013857 | [-0.017536, -0.010341] | **PASS** |
- T-C: not run (pre-registered condition not met: S2 rejected).

### Test differences per season (descriptive; 98.3% CIs, no per-group verdict)

| season | test | n | mean diff | CI low | CI high |
|---|---|---|---|---|---|
| 2015-2016 | T-A | 2744 | -0.015424 | -0.019141 | -0.011930 |
| 2015-2016 | T-B | 2744 | -0.014447 | -0.020771 | -0.008035 |
| 2016-2017 | T-A | 2744 | -0.013684 | -0.018388 | -0.009345 |
| 2016-2017 | T-B | 2744 | -0.012547 | -0.018897 | -0.006093 |
| 2017-2018 | T-A | 2744 | -0.012599 | -0.016206 | -0.008822 |
| 2017-2018 | T-B | 2744 | -0.012633 | -0.020092 | -0.004627 |
| 2018-2019 | T-A | 2744 | -0.014233 | -0.018405 | -0.009980 |
| 2018-2019 | T-B | 2744 | -0.015803 | -0.023042 | -0.008306 |

### Test differences per competition (descriptive; 98.3% CIs, no per-group verdict)

| competition | test | n | mean diff | CI low | CI high |
|---|---|---|---|---|---|
| DEU Bundesliga 1 | T-A | 1224 | -0.013953 | -0.020087 | -0.007833 |
| DEU Bundesliga 1 | T-B | 1224 | -0.017933 | -0.030048 | -0.006392 |
| ENG Premier League | T-A | 1520 | -0.013774 | -0.019442 | -0.008641 |
| ENG Premier League | T-B | 1520 | -0.013440 | -0.022782 | -0.003942 |
| ESP La Liga | T-A | 1520 | -0.013322 | -0.018396 | -0.008362 |
| ESP La Liga | T-B | 1520 | -0.014611 | -0.026198 | -0.002847 |
| FRA Ligue 1 | T-A | 1520 | -0.016792 | -0.022944 | -0.011348 |
| FRA Ligue 1 | T-B | 1520 | -0.017733 | -0.027627 | -0.008453 |
| ITA Serie A | T-A | 1520 | -0.014482 | -0.019626 | -0.009740 |
| ITA Serie A | T-B | 1520 | -0.015273 | -0.023797 | -0.007205 |
| NLD Eredivisie | T-A | 1224 | -0.013937 | -0.020135 | -0.008130 |
| NLD Eredivisie | T-B | 1224 | -0.013502 | -0.022513 | -0.004865 |
| PRT Liga 1 | T-A | 1224 | -0.012094 | -0.017948 | -0.006486 |
| PRT Liga 1 | T-B | 1224 | -0.008942 | -0.016708 | -0.001610 |
| TUR Super Lig | T-A | 1224 | -0.012937 | -0.018914 | -0.006878 |
| TUR Super Lig | T-B | 1224 | -0.008064 | -0.016527 | 0.000335 |

## Secondary metrics (descriptive)

### All scored F rows

| model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|
| Stage 2 baseline | 10976 | 0.205163 | 0.198021 | 0.997499 | 0.515762 |
| P1 | 10976 | 0.201317 | 0.195119 | 0.983514 | 0.521046 |
| Goals-only candidate | 10976 | 0.197139 | 0.192081 | 0.969656 | 0.536352 |

### Per season

| season | model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|---|
| 2015-2016 | Stage 2 baseline | 2744 | 0.209594 | 0.203661 | 1.019741 | 0.490525 |
| 2015-2016 | P1 | 2744 | 0.205516 | 0.200349 | 1.004317 | 0.496356 |
| 2015-2016 | Goals-only candidate | 2744 | 0.201287 | 0.196985 | 0.989871 | 0.513120 |
| 2016-2017 | Stage 2 baseline | 2744 | 0.203323 | 0.195043 | 0.986387 | 0.530612 |
| 2016-2017 | P1 | 2744 | 0.199590 | 0.192411 | 0.972703 | 0.536079 |
| 2016-2017 | Goals-only candidate | 2744 | 0.195882 | 0.189859 | 0.960156 | 0.551385 |
| 2017-2018 | Stage 2 baseline | 2744 | 0.201004 | 0.194018 | 0.980531 | 0.528790 |
| 2017-2018 | P1 | 2744 | 0.197442 | 0.191435 | 0.967932 | 0.536808 |
| 2017-2018 | Goals-only candidate | 2744 | 0.193665 | 0.188729 | 0.955299 | 0.549198 |
| 2018-2019 | Stage 2 baseline | 2744 | 0.206730 | 0.199359 | 1.003336 | 0.513120 |
| 2018-2019 | P1 | 2744 | 0.202720 | 0.196282 | 0.989103 | 0.514942 |
| 2018-2019 | Goals-only candidate | 2744 | 0.197721 | 0.192750 | 0.973300 | 0.531706 |

### Per competition

| competition | model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|---|
| DEU Bundesliga 1 | Stage 2 baseline | 1224 | 0.215798 | 0.206234 | 1.032192 | 0.488562 |
| DEU Bundesliga 1 | P1 | 1224 | 0.211724 | 0.203192 | 1.018239 | 0.495915 |
| DEU Bundesliga 1 | Goals-only candidate | 1224 | 0.206235 | 0.199281 | 1.000305 | 0.506536 |
| ENG Premier League | Stage 2 baseline | 1520 | 0.200691 | 0.194150 | 0.981499 | 0.537500 |
| ENG Premier League | P1 | 1520 | 0.197047 | 0.191225 | 0.967725 | 0.537500 |
| ENG Premier League | Goals-only candidate | 1520 | 0.193186 | 0.188357 | 0.954285 | 0.553947 |
| ESP La Liga | Stage 2 baseline | 1520 | 0.205408 | 0.198990 | 1.001147 | 0.503947 |
| ESP La Liga | P1 | 1520 | 0.201537 | 0.196216 | 0.987824 | 0.502632 |
| ESP La Liga | Goals-only candidate | 1520 | 0.197127 | 0.192958 | 0.973213 | 0.524342 |
| FRA Ligue 1 | Stage 2 baseline | 1520 | 0.212293 | 0.206521 | 1.034918 | 0.479605 |
| FRA Ligue 1 | P1 | 1520 | 0.208016 | 0.203195 | 1.018126 | 0.486184 |
| FRA Ligue 1 | Goals-only candidate | 1520 | 0.202589 | 0.199350 | 1.000393 | 0.510526 |
| ITA Serie A | Stage 2 baseline | 1520 | 0.198583 | 0.193143 | 0.976888 | 0.531579 |
| ITA Serie A | P1 | 1520 | 0.194565 | 0.190087 | 0.962406 | 0.542105 |
| ITA Serie A | Goals-only candidate | 1520 | 0.189799 | 0.186635 | 0.947133 | 0.562500 |
| NLD Eredivisie | Stage 2 baseline | 1224 | 0.202389 | 0.194190 | 0.979673 | 0.539216 |
| NLD Eredivisie | P1 | 1224 | 0.198582 | 0.191315 | 0.965736 | 0.545752 |
| NLD Eredivisie | Goals-only candidate | 1224 | 0.194763 | 0.188389 | 0.952235 | 0.553922 |
| PRT Liga 1 | Stage 2 baseline | 1224 | 0.194664 | 0.187501 | 0.951140 | 0.542484 |
| PRT Liga 1 | P1 | 1224 | 0.191261 | 0.185028 | 0.939045 | 0.546569 |
| PRT Liga 1 | Goals-only candidate | 1224 | 0.188545 | 0.182974 | 0.930104 | 0.559641 |
| TUR Super Lig | Stage 2 baseline | 1224 | 0.212367 | 0.203259 | 1.021455 | 0.505719 |
| TUR Super Lig | P1 | 1224 | 0.208799 | 0.200638 | 1.008518 | 0.515523 |
| TUR Super Lig | Goals-only candidate | 1224 | 0.206282 | 0.198949 | 1.000454 | 0.517974 |

### Rows with snapshot odds (n=10976; columns ['bb_av_h/bb_av_d/bb_av_a'])

Stack and market-only use the frozen DEV+VAL coefficients (descriptive Phase 6 only).

| model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|
| Stage 2 baseline | 10976 | 0.205163 | 0.198021 | 0.997499 | 0.515762 |
| P1 | 10976 | 0.201317 | 0.195119 | 0.983514 | 0.521046 |
| Goals-only candidate | 10976 | 0.197139 | 0.192081 | 0.969656 | 0.536352 |
| Stack | 10976 | 0.191547 | 0.187907 | 0.951044 | 0.548014 |
| Market-only (snapshot) | 10976 | 0.191579 | 0.187937 | 0.951133 | 0.548014 |

### Gap to the Pinnacle closing market (psch/pscd/psca; rows with it, n=10965)

Bookmaker: Pinnacle closing. Closing odds are later than any T-60 forecast: benchmark only. Not comparable with the TEST-era closing-average figures.

| model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|
| Stage 2 baseline | 10965 | 0.205249 | 0.198110 | 0.997921 | 0.515641 |
| P1 | 10965 | 0.201397 | 0.195203 | 0.983908 | 0.520930 |
| Goals-only candidate | 10965 | 0.197213 | 0.192158 | 0.970007 | 0.536161 |
| Pinnacle closing market | 10965 | 0.190938 | 0.187475 | 0.948996 | 0.547378 |
