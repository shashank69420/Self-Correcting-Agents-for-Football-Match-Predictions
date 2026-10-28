# PP decision (v2, revised after a failed numerical check)

selection-period, retrospective, not out-of-sample. Protocol: `pp/PREREGISTRATION_v2.md` (sha256 12bf26792d73fc5cf93323d38d181f5095643b1fc624c1e8235b0757e9f33fe2). PP uses N* = 301 Gauss-Hermite nodes (`results/pp/pp_nodes.json`). Baseline: the frozen P2 goals-only candidate. Only the forecast step differs.

| model | split | log-loss | RPS | Brier |
|---|---|---|---|---|
| baseline | dev | 0.981546 | 0.200082 | 0.194632 |
| pp | dev | 0.983277 | 0.200383 | 0.194932 |
| baseline | val | 0.968042 | 0.192944 | 0.191742 |
| pp | val | 0.971352 | 0.193464 | 0.192280 |
| baseline | pooled | 0.977109 | 0.197737 | 0.193683 |
| pp | pooled | 0.979359 | 0.198109 | 0.194061 |

Rows: DEV 8769, VAL 4291, DEV+VAL 13060.

| split | log-loss PP minus baseline | RPS PP minus baseline | Brier PP minus baseline |
|---|---|---|---|
| dev | +0.001732 | +0.000301 | +0.000300 |
| val | +0.003310 | +0.000520 | +0.000538 |
| pooled | +0.002250 | +0.000373 | +0.000378 |

Decisive: 99% paired week-block CI of the per-row log-loss difference on DEV+VAL (2000 resamples, seed 20261030): [+0.001561, +0.003001].

Reported, not decisive: 99% CI of the per-row RPS difference: [+0.000253, +0.000491].

- (i) DEV log-loss improves: NO
- (ii) VAL log-loss improves: NO
- (iii) 99% CI upper bound < 0: NO

Verdict: **REJECTED**.

## VAL per league (descriptive, no per-league verdict)

| competition | model | n | LogLoss | RPS | Brier |
|---|---|---|---|---|---|
| DEU Bundesliga 1 | baseline | 478 | 0.963376 | 0.193164 | 0.190347 |
| DEU Bundesliga 1 | pp | 478 | 0.967116 | 0.193750 | 0.190885 |
| ENG Premier League | baseline | 610 | 0.951896 | 0.193013 | 0.187735 |
| ENG Premier League | pp | 610 | 0.955196 | 0.193584 | 0.188277 |
| ESP La Liga | baseline | 591 | 0.981875 | 0.193041 | 0.194732 |
| ESP La Liga | pp | 591 | 0.986475 | 0.193886 | 0.195535 |
| FRA Ligue 1 | baseline | 478 | 1.020326 | 0.210037 | 0.204272 |
| FRA Ligue 1 | pp | 478 | 1.021591 | 0.210120 | 0.204354 |
| ITA Serie A | baseline | 599 | 0.980442 | 0.190010 | 0.195149 |
| ITA Serie A | pp | 599 | 0.985031 | 0.190736 | 0.195912 |
| NLD Eredivisie | baseline | 484 | 0.930294 | 0.185577 | 0.183369 |
| NLD Eredivisie | pp | 484 | 0.932759 | 0.185764 | 0.183682 |
| PRT Liga 1 | baseline | 478 | 0.936873 | 0.185477 | 0.184376 |
| PRT Liga 1 | pp | 478 | 0.940465 | 0.186087 | 0.185033 |
| TUR Super Lig | baseline | 573 | 0.976166 | 0.193843 | 0.193291 |
| TUR Super Lig | pp | 573 | 0.978643 | 0.194278 | 0.193790 |
