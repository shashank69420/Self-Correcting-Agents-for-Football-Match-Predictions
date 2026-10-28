# Decision-log extract

Verbatim lines from `DECISIONS.md` (the dated decision log) and the project rules file, copied on
2026-10-29 when both files were removed from the repository tree. They are kept because numbers in
`results/FINDINGS.md` (Gate B and the post-hoc lineup checks) were recorded only there. The full files remain
in the git history.

## From DECISIONS.md

- 2026-10-19 Gate B FAILED (locked spec). Approved: n/a, pre-registered rule.

- 2026-10-19 Gate B diagnosis (/diagnose, read-only; outputs/diagnose/). Class (c) true null
  for the defence term, with (d) weak defence-line proxy as secondary. Evidence: independent
  numpy GLM and independent A/D recomputation reproduce the fit exactly; no rows on or after
  ESTIMATION_CUTOFF; 0/200 within-season placebos pass the gate; MDE for c_def 0.056, power
  99.8% for an attack-sized effect, CI rules out c_def < -0.041. Gate B verdict unchanged: FAILED.
- 2026-10-19 EXPLORATORY (post-hoc, attack-only; chosen after Gate B failed, from training
  data only). The single approved post-hoc spec for Gate B. Frozen c_att = +0.09503 (Gate B
  primary fit), all defence deltas 0, clip [-0.5, 0.5], TEST_INDEX rows with complete features
  on both sides (3786/3829, 98.88%). Result: LogLoss diff +0.000109, 95% paired week-block CI
  [-0.000669, +0.000878] on 3543 covered common rows: no improvement. Placebo +0.000148, CI
  [-0.000677, +0.001007]. No further post-hoc runs for Gate B. Approved: user, 2026-10-19.

## From the project rules

- Gate A (test-period lineup coverage >= 90% full XI): PASSED.
- Gate B: FAILED (2026-10-19). c_att +0.0950 CI [0.0487, 0.1413];
  c_def -0.0022 CI [-0.0413, 0.0368]. Final for the locked spec. Code and
  details are on branch gate-b-lineup.

- Burn-in filter (estimation only, not applied to the adjustments file):
  exclude a match if either team has fewer than 10 prior appearances in the
  full dataset, or if lambda_home or mu_away is outside [0.15, 6.0]. Print
  the number dropped, per season.
