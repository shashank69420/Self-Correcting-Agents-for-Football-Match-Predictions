# PP pre-registration: posterior-predictive forecast (plan item 3)

Written and committed on 2026-10-29 on branch pp, before pp_model.py exists and before any PP forecast is computed or
scored. Nothing in this file changes after the commit "pp: preregistration". The outcome is recorded whichever way it
falls (ACCEPTED, REJECTED, or ACCEPTED on DEV/VAL, UNCONFIRMED).

## Question
The frozen filter forecasts each match from the plug-in rates exp(posterior mean). The filter also carries a variance
for every rating. Does integrating the forecast over that variance (a posterior-predictive score grid) improve the
forecast on DEV/VAL under the same rule that accepted or rejected the P2 steps?

## Baseline
The frozen P2 goals-only candidate, unchanged: `results/p2/candidate_p2.json` (`goals_only.params`: process_noise
0.0025, initial_var 0.15, cold_defence 0.45, clip_rates on, rho -0.04, shots_w 0.5), run with `p2_model.run_filter`
and the home_adv recorded in that file. The run asserts that `run_experiments.load_data` returns the same home_adv.

## Candidate PP (one candidate, nothing fitted, nothing tuned)
Same filter, same parameters, same updates. Only the forecast step changes. At each match, from the predicted states
(after `predict_step`, the states the baseline uses for its means):
- home log-rate mean m_h = attack_mean(home) + defence_mean(away) + home_adv, variance v_h = attack_var(home) +
  defence_var(away); away log-rate mean m_a = attack_mean(away) + defence_mean(home), variance v_a = attack_var(away) +
  defence_var(home).
- Each log-rate is integrated independently over its Gaussian with 9-point Gauss-Hermite quadrature
  (`numpy.polynomial.hermite.hermgauss(9)`, nodes m + sqrt(2 v) x_i, weights w_i / sqrt(pi)). The mean is not re-centred.
- For every node pair (i, j): rate clip to `rate_bounds` as the baseline does, then the baseline's Dixon-Coles grid
  (max_goals 10, rho -0.04, factors floored at 0, grid normalised to sum 1), exactly as `exp_model.dixon_coles_probs`.
- PP grid = sum over (i, j) of w_i w_j times the node-pair grid. Home, draw and away probabilities are read from it as
  the baseline reads them.
- The post-match update is unchanged: it uses the plug-in rates, so PP and the baseline share every state.
- The node count is fixed at 9. It is not a tuning parameter and is not changed after any result.

Implementation checks (tests/test_pp.py), all required before the evaluation runs: (a) zero variance reproduces the
baseline grid to 1e-12; (b) grids are non-negative and sum to 1; (c) 9 and 21 nodes agree to 1e-6 on 50 real matches
(numerical check only); (d) on a synthetic unclipped case the mean goals exceed the plug-in mean by about exp(v/2),
within 1%; (e) goal variance is at least the plug-in variance; and the plug-in probabilities of pp_model reproduce
`p2_model.run_filter` to 1e-12. If a check fails, the evaluation does not run and the failure is reported; the node
count and the method are not changed to make it pass.

## Rows (the P2 selection windows, locked)
Main data from `run_experiments.load_data` (data_pipeline, cache). The filter runs on the non-TEST rows only
(`run_p2.selection_frames`). DEV: 2020-07-01 to 2023-06-30. VAL: from 2023-07-01, excluding TEST_INDEX by row
identity. No TEST_INDEX row is filtered or scored. No FRESH 2015-19 row and no 2026-27 row is used.

## Decision rule
The prompt for this task proposed: primary metric RPS, pooled DEV+VAL, candidate minus baseline; ACCEPT only if the CI
upper bound is below 0 and the point difference is negative on DEV and on VAL separately. It also said that the P2
rule wins where the two differ. They differ in the metric (P2 decides on log-loss) and the P2 rule fixes the CI level
(99%). The P2 rule is therefore used, copied from `p2/PREREGISTRATION.md`, "Selection rule (per experiment)":

> Accept only if all three hold: (i) DEV log-loss improves on the incumbent, (ii) VAL log-loss improves, (iii) the
> 99% paired week-block bootstrap CI (2000 resamples, seed 20261030; `exp_harness.week_block_ci`) on DEV+VAL rows for
> (candidate minus incumbent) per-row log-loss has upper bound below 0. A candidate equal to the incumbent fails (i).

Here the incumbent is the baseline above and the candidate is PP. Log-loss is the mean per-match log-loss
(`exp_harness.row_scores`, probabilities clipped at 1e-15). The S2 version of this rule restricts rows to those with
snapshot odds because S2 uses the market; PP does not use the market, so the rows are all DEV and VAL rows, as for S0
and S1. The code path is `run_p2.scores`, `run_p2.row_loss`, `run_p2.week_ci` at `run_p2.SELECT_LEVEL` and
`exp_harness.accept`. Otherwise REJECT.

Reported, not decisive: RPS and Brier per split and pooled, the RPS difference with its 99% paired week-block CI
(same seed), and the per-league VAL table.

## Run once
`run_pp.py` runs the evaluation once and writes `results/pp/pp_dev_val.json` and `results/pp/pp_decision.md`. It
refuses to run when `results/pp/pp_dev_val.json` exists. A re-run is allowed only to fix a crash before any result was
written; any such fix is recorded in DECISIONS.md.

## Confirmation (only if ACCEPTED)
One attempt on the untouched seasons 2009-2010 to 2013-2014, the 8 leagues in `data_pipeline.LEAGUES`: one call to
`p2_data.fetch_fresh` for those seasons, cleaned as the P2 fresh frame (including its no-Time exception), run as its
own chronological sequence. 2009-2010 is burn-in and never scored; 2010-2011 to 2013-2014 are scored. home_adv and all
parameters stay frozen. One test: mean per-match log-loss, PP minus baseline, 95% paired week-block CI (2000
resamples, seed 20261030); it confirms only if the upper bound is below 0. If the data cannot be loaded in that one
attempt, the outcome is "ACCEPTED on DEV/VAL, UNCONFIRMED". An unconfirmed result never enters a headline claim.
If PP is REJECTED, the confirmation is not run and the 2009-14 seasons stay untouched.

## Recording
FINDINGS section 12 and `results/claims.json` back every number; one dated DECISIONS.md entry records the outcome,
including a rejection. No file in results/fan/, results/p2/, results/experiments/, results/live2627/ or forward/
changes. The anchors stay 0.2057 / 0.2060 / 0.2059 / CHANGE_SCALE 0.
