# Harness report: Stage 2 baseline vs frozen candidate P1

Accepted experiments: ['E1', 'E3', 'E5']. P1 parameters: `{"process_noise": 0.005, "initial_var": 0.3, "cold_defence": 0.3, "clip_rates": true, "rho": -0.04}`.

Holm adjustment over the six experiments (one-sided bootstrap p; acceptance used the locked rule):

| experiment | chosen | dev_logloss | val_logloss | ci99 | p_one_sided | p_holm | verdict |
|---|---|---|---|---|---|---|---|
| E1 | {"process_noise": 0.005, "initial_var": 0.3} | 0.997962 | 0.983396 | [-0.020189, -0.012334] (DEV+VAL) | 0.000500 | 0.002999 | ACCEPTED |
| E2 | {"drift_per_day": 0.0, "season_var": 0.0} | 0.997962 | 0.983396 | [+0.000000, +0.000000] (DEV+VAL) | 1.000000 | 1.000000 | REJECTED |
| E3 | {"cold_attack": 0.0, "cold_defence": 0.3, "clip_rates": true} | 0.997289 | 0.982435 | [-0.001715, -0.000099] (DEV+VAL) | 0.001499 | 0.005997 | ACCEPTED |
| E4 | {"league_k": null} | 0.997289 | 0.982435 | [+0.000000, +0.000000] (DEV+VAL) | 1.000000 | 1.000000 | REJECTED |
| E5 | {"rho": -0.04} | 0.997085 | 0.981172 | [-0.000999, -0.000116] (DEV+VAL) | 0.000500 | 0.002999 | ACCEPTED |
| E6 | {"temperature": 1.2551125450691194, "bias": [0.0464618750007404, -0.03708219747085956, -0.009379677529880844]} | 0.992860 | 0.978388 | [-0.006639, +0.001068] (VAL) | 0.024988 | 0.074963 | REJECTED |

All numbers below are selection-period, retrospective, not out-of-sample. TEST rows are not scored.

## DEV (8769 matches)

### Overall

| model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|
| Baseline | 8769 | 0.20813 | 0.20074 | 1.01150 | 0.51614 |
| Candidate | 8769 | 0.20433 | 0.19785 | 0.99709 | 0.52264 |

### Skill and closing market

Climatology = training-window outcome rates H/D/A [0.4347, 0.2505, 0.3148] (15316 non-TEST matches; in-sample for this reference).

| model | RPS | RPS skill vs clim | n market rows | RPS (market rows) | RPS skill (market rows) | market RPS | clim-to-market share |
|---|---|---|---|---|---|---|---|
| Baseline | 0.20813 | 0.10188 | 8740 | 0.20862 | 0.09922 | 0.19543 | 0.63535 |
| Candidate | 0.20433 | 0.11827 | 8740 | 0.20475 | 0.11590 | 0.19543 | 0.74216 |

Share of the baseline-to-closing-market RPS gap closed by the candidate: 29.29%

### Per season

| season | model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|---|
| 2019-2020 | Baseline | 313 | 0.20826 | 0.19508 | 0.98698 | 0.53994 |
| 2019-2020 | Candidate | 313 | 0.20744 | 0.19476 | 0.98587 | 0.53355 |
| 2020-2021 | Baseline | 2858 | 0.21042 | 0.20446 | 1.02874 | 0.50630 |
| 2020-2021 | Candidate | 2858 | 0.20602 | 0.20106 | 1.01201 | 0.51330 |
| 2021-2022 | Baseline | 2818 | 0.20893 | 0.20220 | 1.01742 | 0.50923 |
| 2021-2022 | Candidate | 2818 | 0.20503 | 0.19920 | 1.00225 | 0.51490 |
| 2022-2023 | Baseline | 2780 | 0.20495 | 0.19609 | 0.99052 | 0.53058 |
| 2022-2023 | Candidate | 2780 | 0.20154 | 0.19353 | 0.97777 | 0.53885 |

### Per competition

| competition | model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|---|
| DEU Bundesliga 1 | Baseline | 918 | 0.21808 | 0.20863 | 1.04716 | 0.50436 |
| DEU Bundesliga 1 | Candidate | 918 | 0.21323 | 0.20490 | 1.02790 | 0.51198 |
| ENG Premier League | Baseline | 1206 | 0.21299 | 0.20105 | 1.01593 | 0.51907 |
| ENG Premier League | Candidate | 1206 | 0.20929 | 0.19830 | 1.00121 | 0.52653 |
| ESP La Liga | Baseline | 1197 | 0.21146 | 0.20701 | 1.04005 | 0.48705 |
| ESP La Liga | Candidate | 1197 | 0.20678 | 0.20345 | 1.02247 | 0.50376 |
| FRA Ligue 1 | Baseline | 1140 | 0.21184 | 0.20401 | 1.02560 | 0.50702 |
| FRA Ligue 1 | Candidate | 1140 | 0.20908 | 0.20172 | 1.01468 | 0.50526 |
| ITA Serie A | Baseline | 1238 | 0.20185 | 0.19798 | 0.99839 | 0.53150 |
| ITA Serie A | Candidate | 1238 | 0.19821 | 0.19520 | 0.98462 | 0.54120 |
| NLD Eredivisie | Baseline | 918 | 0.20052 | 0.19327 | 0.97925 | 0.53922 |
| NLD Eredivisie | Candidate | 918 | 0.19658 | 0.19038 | 0.96346 | 0.54466 |
| PRT Liga 1 | Baseline | 965 | 0.19230 | 0.18794 | 0.95120 | 0.54819 |
| PRT Liga 1 | Candidate | 965 | 0.18949 | 0.18579 | 0.94229 | 0.54819 |
| TUR Super Lig | Baseline | 1187 | 0.21388 | 0.20396 | 1.02469 | 0.50042 |
| TUR Super Lig | Candidate | 1187 | 0.20983 | 0.20095 | 1.01011 | 0.50548 |

### Brier Murphy decomposition: Baseline

| outcome | reliability | resolution | uncertainty | within_bin | brier |
|---|---|---|---|---|---|
| Home | 0.000825 | 0.009147 | 0.081781 | -0.000156 | 0.073303 |
| Draw | 0.000419 | 0.000446 | 0.061979 | 0.000038 | 0.061990 |
| Away | 0.000714 | 0.007874 | 0.072696 | -0.000085 | 0.065450 |
| Total | 0.001958 | 0.017467 | 0.216455 | -0.000203 | 0.200744 |

### Favourite vs underdog: Baseline

| band | n | fav forecast | fav observed | draw forecast | draw observed | dog forecast | dog observed |
|---|---|---|---|---|---|---|---|
| all | 8769 | 0.5608 | 0.5168 | 0.2277 | 0.2469 | 0.2115 | 0.2363 |
| fav p < 0.45 | 2391 | 0.4028 | 0.3973 | 0.2821 | 0.2739 | 0.3151 | 0.3287 |
| 0.45-0.60 | 3278 | 0.5194 | 0.4793 | 0.2474 | 0.2694 | 0.2332 | 0.2514 |
| fav p >= 0.60 | 3100 | 0.7265 | 0.6487 | 0.1650 | 0.2023 | 0.1085 | 0.1490 |

### Brier Murphy decomposition: Candidate

| outcome | reliability | resolution | uncertainty | within_bin | brier |
|---|---|---|---|---|---|
| Home | 0.000357 | 0.010047 | 0.081781 | -0.000079 | 0.072011 |
| Draw | 0.000180 | 0.000543 | 0.061979 | 0.000017 | 0.061633 |
| Away | 0.000267 | 0.008537 | 0.072696 | -0.000215 | 0.064210 |
| Total | 0.000805 | 0.019128 | 0.216455 | -0.000278 | 0.197854 |

### Favourite vs underdog: Candidate

| band | n | fav forecast | fav observed | draw forecast | draw observed | dog forecast | dog observed |
|---|---|---|---|---|---|---|---|
| all | 8769 | 0.5478 | 0.5231 | 0.2375 | 0.2469 | 0.2147 | 0.2300 |
| fav p < 0.45 | 2635 | 0.4016 | 0.4140 | 0.2857 | 0.2691 | 0.3127 | 0.3169 |
| 0.45-0.60 | 3310 | 0.5185 | 0.4834 | 0.2535 | 0.2767 | 0.2279 | 0.2399 |
| fav p >= 0.60 | 2824 | 0.7184 | 0.6714 | 0.1737 | 0.1912 | 0.1079 | 0.1374 |

## VAL (4291 matches)

### Overall

| model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|
| Baseline | 4291 | 0.20083 | 0.19783 | 1.00384 | 0.51783 |
| Candidate | 4291 | 0.19665 | 0.19458 | 0.98117 | 0.52598 |

### Skill and closing market

Climatology = training-window outcome rates H/D/A [0.4347, 0.2505, 0.3148] (15316 non-TEST matches; in-sample for this reference).

| model | RPS | RPS skill vs clim | n market rows | RPS (market rows) | RPS skill (market rows) | market RPS | clim-to-market share |
|---|---|---|---|---|---|---|---|
| Baseline | 0.20083 | 0.12268 | 4291 | 0.20083 | 0.12268 | 0.18572 | 0.65018 |
| Candidate | 0.19665 | 0.14094 | 4291 | 0.19665 | 0.14094 | 0.18572 | 0.74699 |

Share of the baseline-to-closing-market RPS gap closed by the candidate: 27.68%

### Per season

| season | model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|---|
| 2023-2024 | Baseline | 2744 | 0.19912 | 0.19696 | 1.00235 | 0.51822 |
| 2023-2024 | Candidate | 2744 | 0.19492 | 0.19363 | 0.97639 | 0.53098 |
| 2024-2025 | Baseline | 1547 | 0.20387 | 0.19936 | 1.00648 | 0.51713 |
| 2024-2025 | Candidate | 1547 | 0.19972 | 0.19628 | 0.98965 | 0.51713 |

### Per competition

| competition | model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|---|
| DEU Bundesliga 1 | Baseline | 478 | 0.20142 | 0.19708 | 0.99377 | 0.52929 |
| DEU Bundesliga 1 | Candidate | 478 | 0.19645 | 0.19324 | 0.97528 | 0.53766 |
| ENG Premier League | Baseline | 610 | 0.19970 | 0.19279 | 0.97662 | 0.53770 |
| ENG Premier League | Candidate | 610 | 0.19652 | 0.19046 | 0.96512 | 0.54590 |
| ESP La Liga | Baseline | 591 | 0.19933 | 0.20035 | 1.00595 | 0.49577 |
| ESP La Liga | Candidate | 591 | 0.19579 | 0.19739 | 0.99191 | 0.50423 |
| FRA Ligue 1 | Baseline | 478 | 0.21833 | 0.21066 | 1.04806 | 0.47280 |
| FRA Ligue 1 | Candidate | 478 | 0.21446 | 0.20780 | 1.03523 | 0.48536 |
| ITA Serie A | Baseline | 599 | 0.19613 | 0.19985 | 1.00420 | 0.52421 |
| ITA Serie A | Candidate | 599 | 0.19215 | 0.19673 | 0.98916 | 0.53422 |
| NLD Eredivisie | Baseline | 484 | 0.19628 | 0.19097 | 0.97543 | 0.54959 |
| NLD Eredivisie | Candidate | 484 | 0.19121 | 0.18731 | 0.95084 | 0.56405 |
| PRT Liga 1 | Baseline | 478 | 0.19421 | 0.18998 | 0.96193 | 0.51674 |
| PRT Liga 1 | Candidate | 478 | 0.19069 | 0.18751 | 0.95114 | 0.52301 |
| TUR Super Lig | Baseline | 573 | 0.20280 | 0.20071 | 1.06072 | 0.51483 |
| TUR Super Lig | Candidate | 573 | 0.19729 | 0.19598 | 0.98932 | 0.51309 |

### Brier Murphy decomposition: Baseline

| outcome | reliability | resolution | uncertainty | within_bin | brier |
|---|---|---|---|---|---|
| Home | 0.000720 | 0.010399 | 0.081999 | -0.000261 | 0.072059 |
| Draw | 0.000627 | 0.000611 | 0.063959 | -0.000039 | 0.063937 |
| Away | 0.001230 | 0.009556 | 0.070575 | -0.000419 | 0.061830 |
| Total | 0.002578 | 0.020566 | 0.216533 | -0.000719 | 0.197826 |

### Favourite vs underdog: Baseline

| band | n | fav forecast | fav observed | draw forecast | draw observed | dog forecast | dog observed |
|---|---|---|---|---|---|---|---|
| all | 4291 | 0.5690 | 0.5188 | 0.2217 | 0.2589 | 0.2093 | 0.2223 |
| fav p < 0.45 | 1123 | 0.4056 | 0.3624 | 0.2785 | 0.2974 | 0.3159 | 0.3402 |
| 0.45-0.60 | 1622 | 0.5205 | 0.4926 | 0.2451 | 0.2768 | 0.2344 | 0.2306 |
| fav p >= 0.60 | 1546 | 0.7386 | 0.6598 | 0.1558 | 0.2122 | 0.1056 | 0.1281 |

### Brier Murphy decomposition: Candidate

| outcome | reliability | resolution | uncertainty | within_bin | brier |
|---|---|---|---|---|---|
| Home | 0.000263 | 0.011589 | 0.081999 | -0.000088 | 0.070585 |
| Draw | 0.000345 | 0.000570 | 0.063959 | -0.000251 | 0.063483 |
| Away | 0.000434 | 0.010160 | 0.070575 | -0.000331 | 0.060517 |
| Total | 0.001042 | 0.022320 | 0.216533 | -0.000670 | 0.194585 |

### Favourite vs underdog: Candidate

| band | n | fav forecast | fav observed | draw forecast | draw observed | dog forecast | dog observed |
|---|---|---|---|---|---|---|---|
| all | 4291 | 0.5574 | 0.5262 | 0.2311 | 0.2589 | 0.2115 | 0.2149 |
| fav p < 0.45 | 1204 | 0.4039 | 0.3638 | 0.2838 | 0.3106 | 0.3124 | 0.3256 |
| 0.45-0.60 | 1626 | 0.5176 | 0.5031 | 0.2513 | 0.2749 | 0.2311 | 0.2220 |
| fav p >= 0.60 | 1461 | 0.7281 | 0.6858 | 0.1652 | 0.1985 | 0.1067 | 0.1157 |
