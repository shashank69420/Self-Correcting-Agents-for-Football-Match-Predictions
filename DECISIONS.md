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
- 2026-10-25 Experiments session (branch experiments). Pre-registered greedy protocol E1-E6, selection on
  DEV/VAL only, TEST never scored. Approved: user, 2026-10-25 (plan approval; DECISIONS.md append-only,
  odds audit on non-TEST rows, E4 joint k).
- 2026-10-25 E1 ACCEPTED: process_noise 0.005, initial_var 0.3 (grid corner). DEV log-loss 1.011496 ->
  0.997962, VAL 1.003838 -> 0.983396, DEV+VAL diff -0.015803, 99% CI [-0.020189, -0.012334].
  Deviation: first invocation crashed before writing output (missing results dir); identical grid re-run
  once. Approved: n/a, pre-registered rule.
- 2026-10-25 E2 REJECTED: best DEV candidate is drift 0, season_var 0 (= incumbent); every positive drift
  or season extra is worse on DEV and VAL. Approved: n/a, pre-registered rule.
- 2026-10-25 E3 ACCEPTED: cold_attack 0, cold_defence 0.3 (grid edge), clip_rates on. DEV log-loss
  0.997962 -> 0.997289, VAL 0.983396 -> 0.982435, DEV+VAL diff -0.000768, 99% CI [-0.001715, -0.000099].
  Approved: n/a, pre-registered rule.
- 2026-10-25 E4 REJECTED: best DEV candidate is league effects off (= incumbent). All k were worse on DEV
  though slightly better on VAL (0.98184-0.98195 vs 0.98244); VAL is not a selection criterion on its own.
  Approved: n/a, pre-registered rule.
- 2026-10-25 E5 ACCEPTED: rho -0.04 (Dixon-Coles sign; inflates 0-0/1-1). DEV log-loss 0.997289 ->
  0.997085, VAL 0.982435 -> 0.981172, DEV+VAL diff -0.000552, 99% CI [-0.000999, -0.000116].
  Approved: n/a, pre-registered rule.
- 2026-10-25 E6 REJECTED: DEV-fitted T 1.2551, bias [+0.0465, -0.0371, -0.0094]. VAL log-loss 0.981172 ->
  0.978388 (diff -0.002784) but 99% VAL CI [-0.006639, +0.001068] includes 0. Not re-run. Approved: n/a,
  pre-registered rule.
