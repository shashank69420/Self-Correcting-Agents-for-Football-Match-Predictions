# Self-correcting football match prediction (Group B12)

A sequential Bayesian model for football results. Each team has an attack and a defence rating, held as a Gaussian
belief (a mean and a variance), and both are updated after every match. Match forecasts come from Poisson goal rates
with a Dixon-Coles correction for low scores, giving home/draw/away probabilities and a full scoreline grid.

The project was run as a pre-registered, gated study. Each improvement was proposed in writing, committed before its
data was examined, decided once by a fixed rule, and reported whether it passed or failed. Every number in
[`results/FINDINGS.md`](results/FINDINGS.md) is checked by a script against a committed source file.

Data: eight European leagues (Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Eredivisie, Primeira Liga,
Super Lig), seasons 2019-20 to 2025-26, plus four earlier seasons for replication and the start of 2026-27.

## Results at a glance

All figures are from `results/FINDINGS.md` (section in brackets). Negative differences in log-loss mean the newer
model is better.

| What was tested | Result | Verdict |
|---|---|---|
| Static Dixon-Coles vs sequential filter, 3,545 common test matches [2] | RPS 0.2057 vs 0.2060 | the filter alone does not beat the static model |
| Learned filter (P1) vs baseline on the held-out TEST window [6] | log-loss -0.012828, 95% CI [-0.015519, -0.010091] | improvement (retrospective holdout) |
| P1 vs baseline on four untouched seasons, 2015-16 to 2018-19 [9] | -0.013985, 98.3% CI [-0.016001, -0.012097] | replicated |
| Final model (P2: refined grid, shots on target in the update) vs P1 on the same fresh seasons [9] | -0.013857, 98.3% CI [-0.017536, -0.010341] | replicated |
| P1 vs baseline on 563 completed 2026-27 matches, parameters frozen before the season's data was fetched [10] | -0.014830, 97.5% CI [-0.027430, -0.003056] | accepted |
| P2 vs P1 on the same 2026-27 matches [10] | -0.014795, 97.5% CI [-0.030241, -0.000024] | accepted, marginal |
| Forecast averaged over the rating uncertainty (posterior predictive) vs the plug-in forecast, DEV/VAL [12] | worse on DEV and VAL; 99% CI [+0.001561, +0.003001] | rejected |

What did not work, reported as final:
- Surprise-driven updating (the first novelty): validation switched it off; it gave no reliable gain [3].
- Lineup weighting from Transfermarkt starting XIs (the second novelty): Gate B failed [4].
- Stacking the model with pre-match market odds: rejected [9].
- The posterior-predictive forecast: rejected [12]. The model learns in a Bayesian way, but its forecasts use the centre
  of each belief; the variances did not make forecasts better.

The closing betting market is still ahead of the model: on the 2026-27 matches the final model's log-loss is 0.019317
worse than closing odds [10]. Closing odds use information from after the forecast time, so they are a benchmark only.

## How the evaluation was kept honest

- **Fixed windows.** Burn-in before 2020-07-01 (never scored); DEV 2020-07-01 to 2023-06-30 and VAL from 2023-07-01 for
  every selection; a TEST window (Feb 2025 to May 2026) scored once for the main claim; four fresh seasons (2015-16 to
  2018-19) scored once for replication; the 2026-27 snapshot scored once. Seasons 2009-10 to 2013-14 are untouched.
- **Pre-registration.** `p2/`, `live2627/`, `forward/` and `pp/` each hold a `PREREGISTRATION.md` committed before the
  data it governs was fetched or scored. Frozen models are in `results/experiments/candidate_p1.json` and
  `results/p2/candidate_p2.json` (the latter carries its own sha256).
- **One run per test.** The scripts that score a protected window refuse to run a second time.
- **Number checking.** `tools/verify_claims.py` fails if any number in FINDINGS lacks a matching entry in
  `results/claims.json` that points at a tracked file.
- **Forward log.** `forward/predictions.jsonl` is an append-only, hash-chained log of forecasts written before kickoff.

## Repository layout

| Path | Contents |
|---|---|
| `data_pipeline.py` | fixture ingestion (football-data.co.uk via penaltyblog), cleaning, chronological split |
| `stage1_baseline.py`, `stage2_dynamic.py`, `stage3_detector.py` | static Dixon-Coles, the sequential filter, the surprise detector |
| `metrics.py` | RPS, Brier, log-loss and bootstrap helpers |
| `lineup.py`, `lineup_audit.py` | Transfermarkt lineup matching and the Gate B lineup test |
| `exp_model.py`, `exp_harness.py`, `run_experiments.py`, `EXPERIMENTS.md` | P1: learned filter parameters (experiments E1 to E6) |
| `p2_data.py`, `p2_model.py`, `p2_stack.py`, `run_p2.py` | P2: refinements, market stack, fresh-season replication |
| `live2627.py` | frozen models on completed 2026-27 matches |
| `forward_logger.py` | forward forecasts, verification and scoring |
| `fan_features.py`, `fan/` | scoreline markets (over 2.5, both teams to score) and team ratings with uncertainty bars |
| `pp_model.py`, `run_pp.py` | posterior-predictive forecast test |
| `main.py` | runs the baseline stages; `main_original.py` is the original pipeline kept for reference |
| `results/` | every reported result, `FINDINGS.md`, `claims.json`, and the source files they cite |
| `presentation/` | figure script and figures |
| `site/` | offline project website; serve with `python -m http.server -d site 8000` and open http://localhost:8000 (`site/build_data.py` rebuilds `site/data.json` from committed results) |
| `tools/gate.py`, `tools/verify_claims.py` | the verification gate and the claims checker |
| `tests/` | unit and reproduction tests (131) |

## Setup

Python 3.13 on Windows was used; the pinned versions matter (penaltyblog in particular).

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

The fixture cache (`data/`) and run outputs (`outputs/`) are not in the repository. `python main.py` downloads the
fixtures on first use and caches them in `data/`; `python main.py --audit` downloads the Transfermarkt tables.

## Verifying the results

```
python -X utf8 tools/gate.py
```

The gate checks that the working tree is clean on `main`, re-runs the baseline and confirms the anchor numbers (Stage 1
RPS 0.2057, Stage 2 RPS 0.2060, all held-out rows 0.2059, change scale 0), runs the 131 tests, checks every FINDINGS
number against its source, checks that no data or outputs are tracked, and confirms the TEST window was scored once. It
prints `GATE: PASS` on a clean checkout with the fixture cache present (tests that need the cache are skipped without it,
and then the test count will not match). `--fast` skips the baseline re-run.

Read-only checks: `python -X utf8 live2627.py --verify` and `python -X utf8 forward_logger.py --verify`.

## Do not re-run

These commands spend a protected data window and refuse a second run, or would re-score data already used:
`results/experiments/test_once.py` and `results/experiments/split_test.py` (TEST scoring), `run_p2.py --fresh` and
`--test-look`, the default `live2627.py` run, and `run_pp.py --evaluate`. Use the committed results instead. `pytest.ini` limits collection to `tests/` so that a plain
`pytest` never imports a scoring script.


