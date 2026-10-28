# PP pre-registration v2: posterior-predictive forecast (plan item 3)

Written and committed on 2026-10-29 on branch pp, before any DEV/VAL outcome was computed for PP and before the node
count N* was selected. Nothing in this file changes after the commit "pp: preregistration v2". v1
(`pp/PREREGISTRATION.md`, commit 8392c3f) stays committed and unchanged. Every result is labelled "v2, revised after a
failed numerical check" and is recorded whichever way it falls (ACCEPTED, REJECTED, or ACCEPTED on DEV/VAL,
UNCONFIRMED).

## Revision disclosure
v2 was written after v1's pre-registered check (c) failed (9 and 21 Gauss-Hermite nodes did not agree to 1e-6 on 50
real matches; DECISIONS.md, 2026-10-29) and after outcome-free diagnostics (`outputs/diagnose/pp_nodes_check.py`, not
committed). v1's evaluation never ran. No DEV/VAL outcome was computed for PP before this file was committed: a grep of
`outputs/diagnose/*.py` for goals_home, goals_away, outcome, row_scores, LogLoss, RPS, Brier, actual, summary(,
scored(, probability_metrics, week_ci and accept finds no outcome column and no scoring helper. The diagnostics
compared forecasts with forecasts only. Match results enter them only through the filter's own post-match updates,
exactly as in the frozen baseline. v2 was instructed by the owner on 2026-10-29.

## Baseline and candidate (as in v1)
Baseline: the frozen P2 goals-only candidate, unchanged (`results/p2/candidate_p2.json`, `goals_only.params`,
`p2_model.run_filter`, the home_adv recorded in that file; the run asserts that `run_experiments.load_data` returns the
same home_adv). Candidate PP(N*): same filter, same parameters, same updates; only the forecast step changes. No
fitted parameter changes.

At each match, from the predicted states (after `predict_step`): home log-rate mean m_h = attack_mean(home) +
defence_mean(away) + home_adv with variance v_h = attack_var(home) + defence_var(away); away m_a = attack_mean(away) +
defence_mean(home) with v_a = attack_var(away) + defence_var(home). Each log-rate is integrated independently over its
Gaussian with N-node Gauss-Hermite quadrature (`numpy.polynomial.hermite.hermgauss(N)`, nodes m + sqrt(2 v) x_i,
weights w_i / sqrt(pi)); the mean is not re-centred. Every node pair (i, j) gets the baseline's rate clip and the
baseline's Dixon-Coles grid normalised by its own mass, exactly as `exp_model.dixon_coles_probs` (max_goals 10,
rho -0.04, factors floored at 0); the PP grid is the sum over (i, j) of w_i w_j times that grid. Because the two rates
are independent, the grid is computed in separable form: cell (k, l) = sum_ij a_ik M_ij b_jl with a_ik = w_i
P(k | lambda_i), b_jl = w_j P(l | mu_j) and M_ij = 1 / mass_ij, and only the four Dixon-Coles cells carry the extra
N x N factor. This is the same sum, not an approximation. The post-match update is unchanged (plug-in rates).

## Numerical rule for N (outcome-free)
- Reference: the 301-node Gauss-Hermite integration.
- Ladder: N in 9, 21, 41, 81, 161, 301.
- Rows: the 2,000 non-TEST rows used in `outputs/diagnose`: run the filter on the non-TEST work frame
  (`run_p2.selection_frames`, stable date order); positions `np.sort(np.random.default_rng(20261019).choice(n, 2000,
  replace=False))`, n the number of work rows.
- N* is the smallest ladder value whose maximum absolute difference from the reference, over every scoreline cell
  and the home/draw/away probabilities on those 2,000 rows, is below 1e-5. If no value below 301 qualifies, N* = 301.
- Threshold anchor: 1e-5 is about 5% of the half-width of the P2 S2 99% CI, [-0.000296, +0.000072] (half-width
  0.000184; FINDINGS section 9). This is an external anchor, not a value read off the diagnostic gaps.
- No outcome is used to choose N*. Only N* is evaluated; no other node count is scored on outcomes.
- N*, its maximum error and the full ladder are written to `results/pp/pp_nodes.json` and committed before the
  evaluation.

## Decision rule (unchanged from v1)
The owner's v2 instruction says the rule is copied unchanged from v1 and the P2 S2 rule, and describes it as RPS,
pooled DEV+VAL, candidate minus baseline, ACCEPT only if the CI upper bound is below 0 and the point difference is
negative on DEV and on VAL separately. v1 as committed decides on log-loss, because its own instruction said the P2
rule wins where the two differ, and the P2 rule decides on log-loss at 99%. Changing the decisive metric between v1
and v2 would change a locked rule after a failure, so v2 keeps v1's rule unchanged:

> Accept only if all three hold: (i) DEV log-loss improves on the incumbent, (ii) VAL log-loss improves, (iii) the
> 99% paired week-block bootstrap CI (2000 resamples, seed 20261030; `exp_harness.week_block_ci`) on DEV+VAL rows for
> (candidate minus incumbent) per-row log-loss has upper bound below 0. A candidate equal to the incumbent fails (i).

Incumbent = baseline, candidate = PP(N*). Rows: all DEV and VAL rows (PP does not use the market, so the S2 restriction
to rows with snapshot odds does not apply, as for S0 and S1). Code path: `run_p2.scores`, `run_p2.row_loss`,
`run_p2.week_ci` at `run_p2.SELECT_LEVEL`, `exp_harness.accept`. Otherwise REJECT.
Reported, not decisive: RPS and Brier per split and pooled, and the RPS difference with its 99% paired week-block CI
(same helper and seed), so the RPS reading the instruction describes is visible but does not decide.

## Rows (locked, as in v1)
Main data from `run_experiments.load_data` (cache). The filter runs on non-TEST rows only. DEV: 2020-07-01 to
2023-06-30. VAL: from 2023-07-01, excluding TEST_INDEX by row identity. No TEST_INDEX, FRESH 2015-19 or 2026-27 row is
used.

## Implementation checks (tests/test_pp.py), all required before the evaluation
(a) zero variance reproduces the baseline grid to 1e-12; (b) grids are non-negative and sum to 1; (c) the selection
rule above runs and the selected N* meets the 1e-5 criterion on the 2,000 fixed rows; (d) on a synthetic unclipped case
mean goals exceed the plug-in mean by about exp(v/2), within 1%; (e) goal variance is at least the plug-in variance;
and the plug-in forecast of pp_model reproduces `p2_model.run_filter` to 1e-12. If a check fails, the evaluation does
not run and the failure is reported.

## Run once
`run_pp.py --evaluate` writes `results/pp/pp_dev_val.json` and `results/pp/pp_decision.md` and refuses to run when
`results/pp/pp_dev_val.json` exists or `results/pp/pp_nodes.json` is missing. A re-run is allowed only to fix a crash
before any result was written; any such fix is recorded in DECISIONS.md.

## Confirmation (only if ACCEPTED; as in v1)
One attempt on the untouched seasons 2009-2010 to 2013-2014, the 8 leagues in `data_pipeline.LEAGUES`: one call to
`p2_data.fetch_fresh` for those seasons, cleaned as the P2 fresh frame, run as its own chronological sequence.
2009-2010 is burn-in; 2010-2011 to 2013-2014 are scored. All parameters, home_adv and N* stay frozen. One test: mean
per-match log-loss, PP(N*) minus baseline, 95% paired week-block CI (2000 resamples, seed 20261030); it confirms only if
the upper bound is below 0. If the data cannot be loaded in that one attempt: "ACCEPTED on DEV/VAL, UNCONFIRMED". An
unconfirmed result never enters a headline claim. If REJECTED, 2009-14 stays untouched.

## Recording
FINDINGS section 12 (with this revision disclosure in words) and `results/claims.json` back every number; one dated
DECISIONS.md entry records the outcome, including a rejection. No file in results/fan/, results/p2/,
results/experiments/, results/live2627/ or forward/ changes. Anchors stay 0.2057 / 0.2060 / 0.2059 / CHANGE_SCALE 0.
