# LIVE 2026-27, retrospective forecasts (not timestamped before kickoff)

**LIVE 2026-27, retrospective forecasts (not timestamped before kickoff).** Parameters were fixed before 2026-27 data was fetched. Forecasts were recomputed after the matches were played and are not timestamped before kickoff. Team ratings update with each result as it arrives.

Pre-registered in `live2627/PREREGISTRATION.md` (commit 08f6c53757edd45c733602e8c4ed24950e0fe73d). Snapshot `results/live2627/snapshot_20261026.json` (rows sha256 57df218f259c594149edf2e8d9dc6e6e4af55e12d044c08732b777965d336294). Code commit a360eef9a4d41b5c8ddc426aa3e24413fd1e60fe, uncommitted changes when run: no. home_adv 0.20356233139056304 (fixed). P2 frozen file self-hash bf7d5226316fe2cb4473e7120c624802f7dcdbd651b603200747f179728b0e3f.

Checks on forecasts only, before any score (tolerance 1e-12):
- p2_model shots_w 0 vs exp_model P1 (probabilities and rates): max abs difference 0.0e+00 over 19716 concatenated rows.
- M0 vs stage2_dynamic.run_sequential_filter (probabilities): max abs difference 0.0e+00 over 19716 concatenated rows.
- String-dtype cast of L needed for the concatenation: no.

## Rows

- Snapshot rows: 571; completed L rows: 571.
- Excluded, in the forward log (matched on league, season, home, away): 0.
- Excluded, flagged name (WRatio 88 or more, or a club_id alias: post-hoc stricter reading, DECISIONS.md 2026-10-27): 8 rows; flagged teams: Erzurumspor; WRatio flags: none; club_id aliases: Erzurumspor = Erzurum BB (club_id 39722).
  - TUR Super Lig: Amedspor v Erzurumspor, 2026-08-16 19:30
  - TUR Super Lig: Erzurumspor v Galatasaray, 2026-08-21 19:30
  - TUR Super Lig: Genclerbirligi v Erzurumspor, 2026-08-28 19:30
  - TUR Super Lig: Erzurumspor v Konyaspor, 2026-09-05 15:00
  - TUR Super Lig: Besiktas v Erzurumspor, 2026-09-11 18:00
  - TUR Super Lig: Erzurumspor v Samsunspor, 2026-09-20 15:00
  - TUR Super Lig: Alanyaspor v Erzurumspor, 2026-10-10 14:00
  - TUR Super Lig: Erzurumspor v Eyupspor, 2026-10-17 11:30
- Test set: 563 matches; newcomer matches 75, established 488.
- Newcomers (in L, absent from H; kept, cold start): Academico Viseu, Amedspor, Corum, Coventry, Elversberg, Erzurumspor, Hull, La Coruna, Le Mans, Malaga, Santander.

| league | test rows |
|---|---|
| ENG Premier League | 70 |
| ESP La Liga | 89 |
| DEU Bundesliga 1 | 54 |
| ITA Serie A | 70 |
| FRA Ligue 1 | 63 |
| NLD Eredivisie | 81 |
| PRT Liga 1 | 72 |
| TUR Super Lig | 64 |

## Primary tests (pre-registered)

Mean per-match log-loss difference on the test set; 97.5% paired bootstrap CI resampling matches (Bonferroni for two tests; 2000 resamples, seed 20261031). An improvement is accepted only if the upper bound is below 0.

| test | comparison | n | first | second | mean diff | SE | 97.5% CI | half-width | verdict |
|---|---|---|---|---|---|---|---|---|---|
| T1 | M1 P1 minus M0 baseline | 563 | 0.997184 | 1.012014 | -0.014830 | 0.005463 | [-0.027430, -0.003056] | 0.012187 | **ACCEPTED** |
| T2 | M2 P2 goals-only minus M1 P1 | 563 | 0.982389 | 0.997184 | -0.014795 | 0.006735 | [-0.030241, -0.000024] | 0.015108 | **ACCEPTED** |

- T1 (M1 P1 minus M0 baseline): ACCEPTED: an improvement under the pre-registered rule; point estimate -0.014830, 97.5% CI [-0.027430, -0.003056].
- T2 (M2 P2 goals-only minus M1 P1): ACCEPTED: an improvement under the pre-registered rule; point estimate -0.014795, 97.5% CI [-0.030241, -0.000024].

## Secondary (descriptive, no verdict)

### Week-block bootstrap (calendar weeks), 97.5%, 2000 resamples, seed 20261031

| test | mean diff | 97.5% week-block CI | half-width |
|---|---|---|---|
| T1 | -0.014830 | [-0.026156, -0.001631] | 0.012263 |
| T2 | -0.014795 | [-0.027079, -0.002906] | 0.012087 |

### Test set: M0-M2

| model | n | RPS | Brier | LogLoss | Accuracy | mean p(draw) | observed draw rate |
|---|---|---|---|---|---|---|---|
| M0 baseline | 563 | 0.209951 | 0.200542 | 1.012014 | 0.513321 | 0.216383 | 0.241563 |
| M1 P1 | 563 | 0.205675 | 0.197669 | 0.997184 | 0.513321 | 0.227196 | 0.241563 |
| M2 P2 goals-only | 563 | 0.201380 | 0.194733 | 0.982389 | 0.516874 | 0.235478 | 0.241563 |

### Per league

| league | model | n | RPS | Brier | LogLoss | Accuracy | mean p(draw) | observed draw rate |
|---|---|---|---|---|---|---|---|---|
| ENG Premier League | M0 baseline | 70 | 0.218878 | 0.213874 | 1.065401 | 0.457143 | 0.226071 | 0.285714 |
| ENG Premier League | M1 P1 | 70 | 0.211656 | 0.208112 | 1.040842 | 0.457143 | 0.236593 | 0.285714 |
| ENG Premier League | M2 P2 goals-only | 70 | 0.205953 | 0.204651 | 1.024479 | 0.442857 | 0.243792 | 0.285714 |
| ESP La Liga | M0 baseline | 89 | 0.199992 | 0.198283 | 0.993818 | 0.449438 | 0.230047 | 0.280899 |
| ESP La Liga | M1 P1 | 89 | 0.192724 | 0.193239 | 0.974047 | 0.494382 | 0.238614 | 0.280899 |
| ESP La Liga | M2 P2 goals-only | 89 | 0.185816 | 0.188775 | 0.958880 | 0.516854 | 0.241813 | 0.280899 |
| DEU Bundesliga 1 | M0 baseline | 54 | 0.232000 | 0.211401 | 1.051931 | 0.555556 | 0.187702 | 0.203704 |
| DEU Bundesliga 1 | M1 P1 | 54 | 0.225047 | 0.206408 | 1.028080 | 0.518519 | 0.198636 | 0.203704 |
| DEU Bundesliga 1 | M2 P2 goals-only | 54 | 0.211478 | 0.196009 | 0.982268 | 0.537037 | 0.210315 | 0.203704 |
| ITA Serie A | M0 baseline | 70 | 0.196191 | 0.178070 | 0.918033 | 0.614286 | 0.234441 | 0.171429 |
| ITA Serie A | M1 P1 | 70 | 0.196233 | 0.178515 | 0.920757 | 0.614286 | 0.246412 | 0.171429 |
| ITA Serie A | M2 P2 goals-only | 70 | 0.195919 | 0.179022 | 0.919409 | 0.585714 | 0.255433 | 0.171429 |
| FRA Ligue 1 | M0 baseline | 63 | 0.215527 | 0.203269 | 1.026142 | 0.523810 | 0.227508 | 0.238095 |
| FRA Ligue 1 | M1 P1 | 63 | 0.209465 | 0.199213 | 1.006851 | 0.539683 | 0.236622 | 0.238095 |
| FRA Ligue 1 | M2 P2 goals-only | 63 | 0.204729 | 0.195923 | 0.990317 | 0.539683 | 0.237157 | 0.238095 |
| NLD Eredivisie | M0 baseline | 81 | 0.205969 | 0.208190 | 1.067165 | 0.530864 | 0.175917 | 0.283951 |
| NLD Eredivisie | M1 P1 | 81 | 0.205675 | 0.207773 | 1.054536 | 0.506173 | 0.188553 | 0.283951 |
| NLD Eredivisie | M2 P2 goals-only | 81 | 0.199472 | 0.203064 | 1.018807 | 0.518519 | 0.204014 | 0.283951 |
| PRT Liga 1 | M0 baseline | 72 | 0.179398 | 0.180089 | 0.914487 | 0.541667 | 0.225885 | 0.250000 |
| PRT Liga 1 | M1 P1 | 72 | 0.181595 | 0.181940 | 0.924435 | 0.541667 | 0.235085 | 0.250000 |
| PRT Liga 1 | M2 P2 goals-only | 72 | 0.189872 | 0.188242 | 0.952631 | 0.555556 | 0.247266 | 0.250000 |
| TUR Super Lig | M0 baseline | 64 | 0.244403 | 0.215166 | 1.074046 | 0.453125 | 0.220810 | 0.187500 |
| TUR Super Lig | M1 P1 | 64 | 0.234487 | 0.209372 | 1.038873 | 0.437500 | 0.234872 | 0.187500 |
| TUR Super Lig | M2 P2 goals-only | 64 | 0.227541 | 0.203865 | 1.017615 | 0.437500 | 0.241886 | 0.187500 |

### Per league, mean differences

| league | n | T1 mean diff | T2 mean diff |
|---|---|---|---|
| ENG Premier League | 70 | -0.024559 | -0.016363 |
| ESP La Liga | 89 | -0.019770 | -0.015168 |
| DEU Bundesliga 1 | 54 | -0.023851 | -0.045812 |
| ITA Serie A | 70 | 0.002724 | -0.001349 |
| FRA Ligue 1 | 63 | -0.019292 | -0.016533 |
| NLD Eredivisie | 81 | -0.012629 | -0.035730 |
| PRT Liga 1 | 72 | 0.009948 | 0.028196 |
| TUR Super Lig | 64 | -0.035173 | -0.021258 |

### Newcomer matches (a team absent from H) and established matches

| matches | model | n | RPS | Brier | LogLoss | Accuracy | mean p(draw) | observed draw rate |
|---|---|---|---|---|---|---|---|---|
| newcomer | M0 baseline | 75 | 0.250044 | 0.235189 | 1.164173 | 0.346667 | 0.218782 | 0.293333 |
| newcomer | M1 P1 | 75 | 0.236001 | 0.226933 | 1.119524 | 0.400000 | 0.227709 | 0.293333 |
| newcomer | M2 P2 goals-only | 75 | 0.222460 | 0.218255 | 1.080323 | 0.413333 | 0.226839 | 0.293333 |
| established | M0 baseline | 488 | 0.203789 | 0.195218 | 0.988629 | 0.538934 | 0.216015 | 0.233607 |
| established | M1 P1 | 488 | 0.201015 | 0.193172 | 0.978382 | 0.530738 | 0.227117 | 0.233607 |
| established | M2 P2 goals-only | 488 | 0.198141 | 0.191118 | 0.967338 | 0.532787 | 0.236806 | 0.233607 |

| matches | n | T1 mean diff | T2 mean diff |
|---|---|---|---|
| newcomer | 75 | -0.044649 | -0.039201 |
| established | 488 | -0.010247 | -0.011044 |

### Draws: mean predicted probability and observed rate (each model on its own rows)

| model | n | mean p(draw) | observed draw rate |
|---|---|---|---|
| M0 baseline | 563 | 0.216383 | 0.241563 |
| M1 P1 | 563 | 0.227196 | 0.241563 |
| M2 P2 goals-only | 563 | 0.235478 | 0.241563 |
| M3 Stage 1 static DC | 488 | 0.243344 | 0.233607 |
| M4 closing average | 563 | 0.238494 | 0.241563 |

### M3 Stage 1 static Dixon-Coles on its rows (both teams in H; n=488; fitted once on all H, never updated; renormalized rows 0)

| model | n | RPS | Brier | LogLoss | Accuracy | mean p(draw) | observed draw rate |
|---|---|---|---|---|---|---|---|
| M0 baseline | 488 | 0.203789 | 0.195218 | 0.988629 | 0.538934 | 0.216015 | 0.233607 |
| M1 P1 | 488 | 0.201015 | 0.193172 | 0.978382 | 0.530738 | 0.227117 | 0.233607 |
| M2 P2 goals-only | 488 | 0.198141 | 0.191118 | 0.967338 | 0.532787 | 0.236806 | 0.233607 |
| M3 Stage 1 static DC | 488 | 0.205119 | 0.196225 | 0.989038 | 0.514344 | 0.243344 | 0.233607 |

### M4 closing average (avg_ch, avg_cd, avg_ca; overround removed proportionally; n=563 of 563 test rows)

Closing odds are later information than any pre-match forecast: benchmark only.

| model | n | RPS | Brier | LogLoss | Accuracy | mean p(draw) | observed draw rate |
|---|---|---|---|---|---|---|---|
| M0 baseline | 563 | 0.209951 | 0.200542 | 1.012014 | 0.513321 | 0.216383 | 0.241563 |
| M1 P1 | 563 | 0.205675 | 0.197669 | 0.997184 | 0.513321 | 0.227196 | 0.241563 |
| M2 P2 goals-only | 563 | 0.201380 | 0.194733 | 0.982389 | 0.516874 | 0.235478 | 0.241563 |
| M4 closing average | 563 | 0.195862 | 0.190903 | 0.963072 | 0.536412 | 0.238494 | 0.241563 |

Gap, model minus M4 (positive: the market is better):

| model | n | LogLoss gap | RPS gap | Brier gap |
|---|---|---|---|---|
| M0 baseline | 563 | 0.048942 | 0.014088 | 0.009640 |
| M1 P1 | 563 | 0.034112 | 0.009813 | 0.006766 |
| M2 P2 goals-only | 563 | 0.019317 | 0.005518 | 0.003830 |

