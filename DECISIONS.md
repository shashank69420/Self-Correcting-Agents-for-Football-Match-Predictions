# Decisions log

Every deviation, failed gate and post-hoc run, with date, decision and approver.

- 2026-10-19 Gate B FAILED (locked spec). Approved: n/a, pre-registered rule.
- 2026-10-19 Process: penaltyblog pinned to 1.12.3; cache is data/fixtures_raw.pkl.
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
