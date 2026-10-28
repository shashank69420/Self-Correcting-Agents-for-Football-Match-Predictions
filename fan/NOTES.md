# Fan features: read-only findings (Phase 1)

Session: Fan-features, branch demo, 2026-10-28. Nothing in this file changes a model, a parameter or a verdict.

Parameters were fixed before 2026-27 data was fetched. Forecasts were recomputed after the matches were played and are
not timestamped before kickoff.

## (a) The P2 filter and the final team states

- `p2_model.run_filter(df, params, home_adv)`: "Pre-match forecasts for every row of df (index and stable date order
  as exp_model.run_filter)". It returns one row per match with `pred_home_win`, `pred_draw`, `pred_away_win`,
  `lambda_home`, `mu_away` (after the clip) and `shots_weight`. The team states are local variables (`states = {}`),
  so the function does not expose them.
- The states are `stage2_dynamic.TeamState` objects with `attack_mean`, `attack_var`, `defence_mean`, `defence_var`.
  Each match calls `predict_step(state, process_noise)` (adds the process noise to both variances) and then
  `update_step(home_state, away_state, goals_home, goals_away, lambda_home, mu_away)`, which changes the two objects in
  place. `p2_model` imports `update_step` into its own namespace (`from stage2_dynamic import TeamState, predict_step,
  update_step`) and `run_filter` calls that module-level name.
- `forward_logger.snapshot_states(history, params, home_adv)` gets final states by patching `exp_model.update_step`
  with a recorder that keeps the state objects and calls the original. It is hard-wired to `exp_model`, so it cannot
  be imported for P2 unchanged. Decision: `fan_features.final_states` uses the same wrapping approach on
  `p2_model.update_step` (`unittest.mock.patch.object`), records the objects only and copies no filter maths. Neither
  file is edited.
- Final state means the state after the team's last `update_step`, with no further `predict_step`. A forecast for
  the next match would add one process noise (0.0025) to each variance first; the ratings use the stored state.
- Parameters: `live2627.load_models()` (frozen-blob guard, `run_p2.load_p1`, `run_p2.load_frozen` self-hash, and the
  check against the pre-registered P2 parameters and home_adv). `p2_model.split_params(params)` fills the
  `exp_model.make_params` defaults: `rate_bounds` (0.15, 6.0) from `exp_model.DEFAULT_PARAMS`, `clip_rates` True, `rho`
  -0.04, `shots_w` 0.5. home_adv 0.20356233139056304 comes from `candidate_p2.json` and equals `live2627.HOME_ADV`.

## (b) The score grid, the draw correction and the clip

- The clip is applied in `p2_model.run_filter`: `lambda_home = min(max(lambda_home, low), high)` and the same for
  `mu_away`, with `low, high = params['rate_bounds']`, when `params['clip_rates']` is true.
- `exp_model.dixon_coles_probs(lambda_home, mu_away, rho=0.0, max_goals=10)`: builds
  `np.outer(poisson.pmf(goals, lambda_home), poisson.pmf(goals, mu_away))` for 0..max_goals, multiplies the four
  low-score cells by `max(1 - lambda*mu*rho, 0)`, `max(1 + lambda*rho, 0)`, `max(1 + mu*rho, 0)`, `max(1 - rho, 0)`
  (rows home goals, columns away goals), renormalises, and returns only (home, draw, away). It accepts `max_goals` but
  does not return the grid.
- Decision: the market grid is a thin reimplementation of those lines in `fan_features.score_grid`, used at
  max_goals 30, with the Poisson product mass (before the correction) checked to be at least 1 - 1e-7. A test checks
  its 1X2 against `dixon_coles_probs` to 1e-12 at max_goals 10 and 30.

## (c) The live test set and VAL

- `live2627.load_history()` (data_pipeline's frame with `is_test` set from TEST_INDEX, after both home_adv asserts),
  `live2627.live_frame(snapshot['rows'])` on `results/live2627/snapshot_20261026.json`,
  `live2627.concatenate(history, live)` (handles the string-dtype mismatch; no cast was needed),
  `live2627.data_checks(history, live)` (name audit with `CLUB_ID_ALIASES`), `live2627.forward_state()` and
  `live2627.select_scored(both, history, forward_keys, flagged)`.
- Counts on 2026-10-28: H 19,145 rows, L 571, concatenated 19,716; TEST_INDEX 3,829 rows; live test set 563;
  excluded 0 forward-log rows and 8 rows of the flagged alias Erzurumspor (= Erzurum BB, club_id 39722).
- Shots on target `hst`, `ast` are present in both frames (L 100% of rows complete, H 99.83%).
- VAL: `exp_harness.split_index` with `VAL_START` 2023-07-01, i.e. H rows not in TEST_INDEX dated on or after
  2023-07-01. L rows are not part of VAL. No metric is computed on a TEST_INDEX row.

## Interpretation notes

- The model has no intercept. A team's attack and defence means are only defined up to a shared shift that home_adv
  and the other teams absorb, so uncentred exp(mean) values are not interpretable. Factors are therefore centred
  within each league across its active 2026-27 teams: exp(mean - mean of the means).
- `defence` here is a concession tendency: the away rate is exp(away attack + home defence). A lower defence factor is
  better.
- The filter is a diagonal Gaussian (Laplace-style) approximation. Bars of exp(centred mean +/- 1 sd) use the model's
  own variance, ignore the uncertainty of the centring and have not been checked for coverage.

## Update equations (written 2026-10-28 from stage2_dynamic.py; the same author wrote the code under test)

For a match with home team h, away team a, goals (g_h, g_a), process noise q and home advantage H:

1. Predict, both teams, before the forecast: var_att(t) += q and var_def(t) += q.
2. Rates: lambda = clip(exp(att(h) + def(a) + H)) and mu = clip(exp(att(a) + def(h))), clip to `rate_bounds`.
3. Effective goals: y_h = (1 - w) g_h + w c SoT_h and y_a likewise (w = 0 when a row has no shots on target).
4. Precisions, using the variances after step 1: P_att(h) = 1/var_att(h) + lambda; P_def(a) = 1/var_def(a) + lambda;
   P_att(a) = 1/var_att(a) + mu; P_def(h) = 1/var_def(h) + mu.
5. Variances: each of those four variances becomes 1/P (all four use the same lambda and mu).
6. Means: att(h) += (y_h - lambda)/P_att(h); def(a) += (y_h - lambda)/P_def(a); att(a) += (y_a - mu)/P_att(a);
   def(h) += (y_a - mu)/P_def(h).
7. A team first seen starts with both means 0 and both variances initial_var; if it first appears after the first
   season of its league, attack mean -cold_attack and defence mean +cold_defence instead.

The variances follow from steps 1, 4 and 5 given only lambda and mu per match, in processing order. A plain-loop
recomputation of the final sd values therefore takes lambda and mu from the model's own output and checks the
variance bookkeeping and the capture of the final states (`tests/test_fan_independent.py`). It does not check the
rates, which come from the model, and it is not independent of the model: the equations above were written by the
author of both the code and the test. Neither is described as independent in any deliverable.

## Reading of the sd-against-matches check (replaces the earlier wording)

The expectation that defence sd falls as matches played rises did not hold: defence sd rises with matches played
(Spearman +0.456) while attack sd falls (Spearman -0.396); n = 139 established teams.

- The smallest |rho| that is significant at the usual two-sided level with n = 139 established teams is about 0.17
  (normal approximation, n minus one in the denominator). That is a significance threshold, not a power calculation,
  and it applies to established teams only.
- The same sign pattern appears in a synthetic simulation (seed 20261028, n = 136 synthetic established teams) built
  from the model's own prior and fitted parameters with no real data. That shows what the model implies under the
  stated design, in which the weakest teams leave each season; it is not a football finding and it does not separate
  the filter's variance dynamics from that exit rule.
- Every rating bar is labelled "model uncertainty, not measured accuracy", and the defence bars carry the note that
  they do not narrow with more matches, a property of the model, not of the team. The fan page does not exist yet
  (not started in this session): both strings are fields in `results/fan/ratings.json` for it to display.
