# Fan features: final report

Parameters were fixed before 2026-27 data was fetched. Forecasts were recomputed after the matches were played and are not timestamped before kickoff.

Branch demo, 2026-10-28. Everything here is descriptive: no test, no claim. The gate output is in `fan/GATE_RESULT.txt`.
Every figure below is a value in `results/claims.json` (the id is in the last column), produced by
`fan_features.py --ratings` and written to the committed file named in that claim. This report adds no statistics.

## What changed

- The ratings-check reading was corrected in `results/fan/ratings_check.md` and `fan/NOTES.md`. It now says, in order,
  that the expectation that defence sd falls as matches played rises did not hold; that defence sd rises while attack
  sd falls; and the number of established teams. The number of teams is beside every statistic.
- The claim that the null result was not underpowered was dropped. The report gives the smallest correlation that is significant at the usual
  two-sided level for established teams only. It is a significance threshold, not a power calculation.
- `fan/NOTES.md` gained the update equations. `tests/test_fan_independent.py` recomputes each team's final sd with
  plain loops from them and matches the committed ratings to a tolerance below one in a billion. It takes the match
  rates from the model's own output and was written by the author of the code, so it is not described as independent.
- A synthetic simulation with a pinned seed (`ratings_sim.json`) shows what the model implies, not a football finding.
- `results/fan/ratings.json` carries the label "model uncertainty, not measured accuracy" on every team record and, on
  every league, the note that defence bars do not narrow with more matches, that this most likely reflects how the
  model's variance behaves, and that it is unconfirmed.
- Both committed markets and metric files are unchanged; a test pins them byte for byte against the base commit.
  `fan_features.py --markets` now only verifies them.
- The remaining outputs from the first fan brief were completed: `model_constants.json`, `sample_forecasts.json` and
  `tests/test_fan.py`.
- `results/FINDINGS.md` gained a new section 11 and `results/claims.json` gained fourteen entries (ids starting `fan_`).

## Figures and their claims

| Figure | Value | Claim id |
|---|---|---|
| Established teams in the ratings | 139 | fan_n_established |
| Spearman, matches played with defence sd | +0.456 | fan_spearman_defence |
| Spearman, matches played with attack sd | -0.396 | fan_spearman_attack |
| Smallest |rho| significant at the usual level, established teams | 0.17 | fan_smallest_significant_rho |
| Smallest defence sd across established teams | 0.177 | fan_defence_sd_min |
| Largest defence sd across established teams | 0.240 | fan_defence_sd_max |
| Smallest defence-bar half-width factor | 1.19 | fan_bar_factor_min |
| Largest defence-bar half-width factor | 1.27 | fan_bar_factor_max |
| Newcomers with both sds above their league's established median | 10 | fan_newcomers_larger |
| Newcomers | 10 | fan_newcomers_n |
| Simulation seed | 20261028 | fan_sim_seed |
| Synthetic established teams | 136 | fan_sim_n_established |
| Simulation, defence Spearman | +0.236 | fan_sim_spearman_defence |
| Simulation, attack Spearman | -0.130 | fan_sim_spearman_attack |

## What remains open

- The fan page and the dashboard were not started, as instructed. The bar label and the defence note exist only as data
  fields and in `ratings_check.md`; no page text has been built or looked at.
- The defence note was reworded after review: the simulation reproduced the signs but could not separate the
  filter's variance behaviour from team selection (its design removes the weakest teams each season), and a variant
  without that exit rule was not run. The note therefore calls the effect unconfirmed.
- The tables that were in `results/fan/markets_calibration.md` and the figures in `fan/NOTES.md` that had no claim
  were deleted from those files rather than claimed. The values remain in the JSON data files, which are not
  claim-checked.
- Two choices were taken by default and need review: the new FINDINGS section, and the update of the expected test count
  in `tools/gate.py` (see `DECISIONS.md`).
- The plain-loop check does not test the rates. The rates are the model's own, and the frozen filter has no separate
  reference implementation here.
- `README.md` does not exist in the repository and was not created.
- The partial correlations from the diagnosis are post-hoc exploratory and are kept in `DECISIONS.md` only.
- The gate's branch check expects `main` and fails on `demo`; nothing else should fail (see `fan/GATE_RESULT.txt`).
