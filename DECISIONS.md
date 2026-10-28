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
- 2026-10-25 Frozen candidate P1 = E1 + E3 + E5 (process_noise 0.005, initial_var 0.3, cold_defence 0.3,
  clip_rates on, rho -0.04). Not evaluated on TEST in this session. Odds audit: non-closing odds timing not
  established (source blocked). Approved: n/a, pre-registered rule.
- 2026-10-25 Odds timing ESTABLISHED (stated schedule, not per-row timestamps); football-data notes.txt, read 2026-10-25: "Betting odds for weekend games are collected Friday afternoons, and on Tuesday afternoons for midweek games." Approved: n/a, verification.
- 2026-10-25 One-shot TEST scoring of frozen P1 (only TEST scoring of P1; retrospective): log-loss P1 minus baseline -0.012828 on 3829 rows, 95% week-block CI [-0.015519, -0.010091], upper bound < 0 => ACCEPTED as a TEST improvement. Approved: user, pre-registered rule.
- 2026-10-26 DESCRIPTIVE split of the already-scored TEST rows (post-scoring, not a test, no new comparison): 1 of 3829 rows (1 of 3545 common) has a baseline rate outside [0.15, 6.0]; it contributes -0.02% of P1 total log-loss gain, so the TEST gain does not depend on outside rows. Approved: user.
- 2026-10-26 Exceptions X1-X5 for the verification-gate task: X1 create tools/, results/sources/, results/audit/, .claude/commands/gate.md; X2 create .claude/settings.json (none existed); X3 append-only sections in CLAUDE.md; X4 edit results/FINDINGS.md; X5 copy the TEST scripts from the scratchpad into results/experiments/. Approved: user, 2026-10-26.
- 2026-10-26 Gate A audit re-run (python main.py --audit, results/audit/): strictly matched 19,140 of 19,145; test period 3829/3829 matched, 3826 with both sides 11 starters (99.92%); GATE A PASSED. sha256 of data/*.gz identical before and after (hash_before.txt, hash_after.txt). Approved: user.
- 2026-10-26 Stages 4 and 5 recorded from AIML_demo_stage5_2026-09-27.ipynb (copied byte-identical, sha256 53e3dc08...b9f77, to results/sources/; main-cell output in stage45_notebook_output.txt). Transfermarkt freeze: upstream README (read 2026-10-25) says current to 6 July 2026; the local download date is not recorded. Approved: user.
- 2026-10-26 TEST reproduction run of results/experiments/test_once.py and split_test.py (copied unmodified, sha256 identical): log-loss difference -0.012828, CI [-0.015519, -0.010091], matching the original to 6 decimals (test_once_repro.txt). A reproduction, not a new test; no parameter changed. Approved: user.
- 2026-10-26 Deviations: (a) gate check "git status clean" allows staged files so it can run before a commit, and fails on unstaged or untracked ones; (b) tests/test_lineup.py imports pytest, which is not installed, so the gate runs the other test files and lists test_lineup as SKIPPED; (c) results/sources/transfermarkt_readme_raw.md is the byte-exact download, kept next to transfermarkt_readme.txt because deletion was not permitted. Approved: pending user review.
- 2026-10-26 Approved exception: tools/gate.py now expects branch main instead of experiments (for use after the merge); nothing else in the gate, anchors, ownership.txt or claims.json changed. Until the merge the branch check fails on experiments. Approved: user, 2026-10-26.
- 2026-10-26 Approved exception: tools/gate.py tests check runs pytest on tests/ when pytest is importable (unittest otherwise) and requires a total of 45; the gate runs pytest on tests/ only because a plain pytest run collects results/experiments/split_test.py (matches *_test.py), whose module code re-runs the TEST split and appends to test_once.md. Approved: user, 2026-10-26.
- 2026-10-26 Approved exception: ownership check compares against fixed base 7cf1b3b (header line "# base:" in tools/ownership.txt) instead of the merge-base. Result: 49 files changed, 4 outside the allowlist (lineup.py, main.py, stage3_detector.py, tests/test_lineup.py, the gate-b-lineup work merged with experiments), not the expected 45 allowed; the ownership check FAILS pending the user's decision. Approved: user (change); allowlist unchanged.
- 2026-10-26 Deviation: one plain pytest run (not the gate) collected split_test.py and appended the descriptive split to results/experiments/test_once.md; the file was restored from git before any commit. It was a deterministic rerun of an existing script, not a new test, and changed no committed file.
- 2026-10-26 Approved post-hoc exception: ownership base is 17af108f3be5159f4cf34269887d072074b1fba2, the parent of the first exp: commit cfad232 (the experiments fork point), replacing 7cf1b3b. Fork-point diff 7cf1b3b..17af108 is exactly five files: lineup.py, main.py, stage3_detector.py, tests/test_lineup.py (gate-b-lineup work) and DECISIONS.md (11 lines added, 0 removed: the 2026-10-19 Gate B entries). DECISIONS.md stays append-only only; no path from that list was added to the allowlist and the append-only check is unchanged. Approved: user, 2026-10-26.
- 2026-10-26 Approved exception: ownership check lists changed files with git diff --cached --name-only <base> (committed plus staged) instead of the written <base> HEAD, so the pre-commit gate also sees staged files; on a clean tree the two lists are identical. The check is a new function ownership_failures; tests/test_gate.py gains one test (main.py fails, allowed paths pass, a removed line in an append-only file fails); expected pytest total in tools/gate.py moves from 45 to 46. Approved: user, 2026-10-26.
- 2026-10-26 Approved exception: new pytest.ini (testpaths = tests; norecursedirs results data outputs venv .git; addopts --ignore=results) so a plain pytest run cannot collect results/experiments/split_test.py or test_once.py, the only pattern-matching files outside tests/ (checked before any pytest run). pytest.ini added to tools/ownership.txt as one line, approved by the user as post-hoc. Plain python -m pytest -q from the root: 46 passed, results/experiments/test_once.md unchanged.
- 2026-10-26 Approved exception: results/FINDINGS.md section 7 gains one sentence (no numbers) disclosing the earlier accidental rerun of the already-scored TEST comparison. Approved: user, 2026-10-26.
- 2026-10-26 Forward-logger session (branch forward-logger). Exceptions granted by the session prompt: create
  forward_logger.py, tests/test_forward.py, forward/PREREGISTRATION.md, forward/predictions.jsonl,
  forward/score_report.md; append-only sections in DECISIONS.md and CLAUDE.md; tools/ownership.txt gains exactly
  those four files plus forward/predictions.jsonl as append-only; results/FINDINGS.md section 8 text replaced, no
  numbers; the forward logger may read completed seasons 2019-2020 to 2025-2026 from data/fixtures_raw.pkl, while
  2026-2027 and the fixture list are always fetched fresh. This supersedes PLAN.md session B's outputs/forward/
  predictions.csv and "must not edit any existing file". Approved: user, 2026-10-26 (session prompt).
- 2026-10-26 Preflight: duckdb is unpinned in requirements.txt; this worktree's venv has duckdb 2.0.0 while the
  main checkout (C:\dev\b12) and b12-lineup venvs have 1.5.6. duckdb is used only by lineup_audit.py (--audit
  fallback), not by main.py, Stages 1-3 or the forward logger; anchors unchanged (0.2057 / 0.2060 / 0.2059 /
  CHANGE_SCALE 0, 46 passed). Not changed. Approved: n/a, recorded as instructed.
- 2026-10-26 Forward source discovery (read-only). A: penaltyblog FootballData(league, '2026-2027') for the 8
  leagues returned 54 to 89 rows each, all played (0 unplayed), latest 2026-10-21. B: fixtures.csv (HTTP 200,
  Last-Modified Fri, 23 Oct 2026 13:46:58 GMT) had 194 rows, 21 Div codes including all 8 expected, Date dd/mm/yyyy,
  Time HH:MM (0 missing), kickoffs 2026-10-23 17:30 to 2026-10-26 20:00, pre-closing and closing odds columns.
  Chosen: B (upcoming fixtures). notes.txt: time zone not stated; fixtures-file update frequency not stated.
  UK-local reading supported by kickoff slots (Bundesliga 15:30 CET shown as 14:30). Approved: n/a, prompt rule.
- 2026-10-26 Forward design choices (session prompt says decide and log): (1) a kickoff exactly 3h away is refused
  (strict > 3h), matching --verify; (2) ambiguous or nonexistent UK local times are refused; (3) exp_model.run_filter
  keeps states internal, so the logger records the TeamState objects run_filter passes to its own update_step
  (unittest.mock.patch.object, wrapping the original) and forecasts with predict_step and dixon_coles_probs; models
  with drift, season variance or league effects are rejected by that wrapper (neither model uses them); (4)
  metrics.paired_week_block_ci fixes seed 20260922, so the CI uses a same-algorithm function with a seed argument
  (20261027), tested equal to the helper at 20260922; (5) the claim is evaluated once, at the first --score run with
  >= 600 scored rows; (6) --verify also checks that the committed log is a byte prefix of the working file (detects
  tail truncation, which a hash chain alone cannot); (7) odds_snapshot keeps the raw CSV strings; (8) code_dirty =
  any git status entry other than forward/predictions.jsonl and forward/score_report.md. Approved: n/a, prompt rule.
- 2026-10-26 Forward commit order: logger and tests are committed before the first real run ("forward: logger and
  tests"), then the first log is committed separately ("forward: first log"), instead of the single commit "forward:
  logger, tests and first log" named in the session prompt, so that every logged row's code_commit contains the code
  that produced it and code_dirty is false. Choice (4) is implemented by running metrics.paired_week_block_ci itself
  with numpy's default_rng patched to seed 20261027 for that call (it checks the helper draws exactly once), so no
  bootstrap code is copied. candidate_p1.json is CRLF in this working copy: params_sha256 is of the on-disk bytes
  (74d14ea8...); the git blob (LF) hashes to a04d1755...; the logger's freeze check compares the parsed params with
  the frozen values, which does not depend on line endings. Approved: n/a, prompt rule (decide and log).
- 2026-10-26 Forward tests: 15 in tests/test_forward.py, all pass; full suite 61 passed. T1 replay: 12 cached rows
  (4 each in 2023-2024, 2024-2025, 2025-2026) x 2 models, max abs difference 0.0 (tolerance 1e-12). tools/gate.py
  expects exactly 46 tests, so its tests check will report 61; the anchor is not edited. Approved: n/a, recorded.
- 2026-10-26 Forward first real run (code 785b7f39, code_dirty false), 03:58 UTC: history 19,716 played rows through
  2026-10-21T18:00:00Z (the 2026-2027 results file lags the fixtures file); 11 newcomers seen only in 2026-2027.
  fixtures.csv: 194 rows, 75 in the 8 leagues, 6 logged (TUR 3, FRA 1, PRT 1, ESP 1; kickoffs 2026-10-26T16:00:00Z
  to 20:00:00Z), 69 refused as kickoff passed, 0 unknown teams. --verify PASS; second run logged 0 (6 already
  logged), file bytes unchanged. --score: 6 logged, 0 scored, 6 pending. Approved: n/a, pre-registered rule.
- 2026-10-26 Gate run after forward Step 6: FAIL (2). Branch check (expects main) as anticipated; tests check
  "actual 61, expected 46": 46 existing tests unchanged and passing plus 15 in tests/test_forward.py, 61 passed.
  /diagnose (outputs/diagnose/forward_gate_tests.txt): class (d) spec problem, the fixed EXPECTED_TESTS anchor
  conflicts with adding test_forward.py while tools/gate.py may not be edited. Not fixed; anchor not edited.
  Options: A [post-hoc] EXPECTED_TESTS 46 -> 61 (recommended); B [post-hoc] 46 existing plus the test_forward
  count; C leave failing. Approved: pending user decision.
- 2026-10-26 Post-hoc approved exception: tools/gate.py EXPECTED_TESTS 46 -> 61 (one line; no other gate, anchor,
  ownership.txt or claims.json change). tests/test_forward.py added 15 tests, all passing; the 46 existing tests are
  unchanged. Resolves the tests-count failure logged above (option A). Approved: user, 2026-10-26.
- 2026-10-26 Pre-commit read-only checks for that exception: (1) the bootstrap seed reaching numpy's default_rng
  inside forward_logger --score is 20261027, and the CI equals an independent recomputation with that seed; the
  unpatched metrics helper would use its hardcoded 20260922 (metrics.py not touched). (2) The fresh 2026-2027
  results source holds 0 completed matches dated 2026-10-22 to 2026-10-25 for each of the 8 leagues (latest result
  per league 2026-10-18 to 2026-10-21), so the first log's history is as current as the source allows; history and log
  unchanged. Approved: n/a, verification requested by user.
- 2026-10-26 Post-hoc approved exception: the forward logger's CI seed is now explicit and self-contained. Finding:
  metrics.paired_week_block_ci has a hardcoded seed (20260922) and the logger previously reached seed 20261027 by
  monkeypatching numpy.random.default_rng around a call to that helper (forward_logger.week_block_ci,
  mock.patch.object on metrics.np.random). It is replaced by paired_week_block_ci_seeded(delta, weeks, seed,
  n_resamples=2000) in forward_logger.py, which implements the same algorithm (group deltas by calendar week,
  resample weeks with replacement, 2.5% and 97.5% quantiles of the resampled mean deltas) and is called from --score
  with seed 20261027. The metrics helper is not used by the forward logger any more and metrics.py is unchanged.
  forward/PREREGISTRATION.md is unchanged: its rule (2000 resamples, seed 20261027, same algorithm as the metrics
  helper) is implemented as written. No outcome has been scored (6 pending), so no result depends on the change.
  Three tests added to tests/test_forward.py: equivalence with the metrics helper at seed 20260922 (1e-12), seed is
  used, pinned interval [-0.008326419307179747, 0.14718068232151577] at seed 20261027 on a fixed input; the earlier
  test of the monkeypatched helper was replaced by test_ci_from_600_scored. Approved: user, 2026-10-26.
- 2026-10-26 Post-hoc approved exception: tools/gate.py EXPECTED_TESTS 61 -> 64 (one line; pytest --collect-only -q
  collects 64: 61 plus the 3 seed tests); nothing else in the gate changed. Diagnosis of the earlier 46 vs 61 failure
  (class d, spec conflict; pytest collect 61, unittest 39 because test_lineup's pytest-style functions are not run
  by unittest, no test failed) is in outputs/diagnose/test_count_diagnosis.txt, local because outputs/ is
  gitignored. Approved: user, 2026-10-26.
- 2026-10-26 Deviation: while writing the diagnosis file I included an rm of a scratch counts file
  (outputs/diagnose/.tmp_counts.txt) in a command; the permission system denied it and nothing was deleted. The
  scratch file remains in the gitignored outputs/ folder. Approved: n/a, disclosure.
- 2026-10-26 P2 session (branch p2). Exceptions granted by the session prompt: create p2_data.py, p2_model.py,
  p2_stack.py, run_p2.py, tests/test_p2.py, p2/PREREGISTRATION.md, results/p2/*.md and *.json; DECISIONS.md and
  CLAUDE.md append-only; claims.json entries appended only; results/FINDINGS.md gains a new section 9 only;
  tools/ownership.txt gains exactly those new paths; tools/gate.py changes only EXPECTED_TESTS, to the collected
  total. exp_model.py, stage*.py, metrics.py, exp_harness.py, forward_logger.py and forward/ are not edited.
  Approved: user, 2026-10-26 (session prompt).
- 2026-10-26 P2 preflight: branch p2, clean tree; pandas 3.0.6, numpy 2.5.4, scipy 1.18.1, statsmodels 0.15.0,
  penaltyblog 1.12.3; gate: anchors 0.2057 / 0.2060 / 0.2059 / CHANGE_SCALE 0, 64 tests, claims, hygiene, ownership
  and test-once PASS, only the branch check FAILS (expects main). candidate_p1.json params equal both the
  incumbent.json overrides and the accepted E1/E3/E5 choices; calibration null. Approved: n/a, recorded.
- 2026-10-26 P2 readings taken before any fresh fetch (prompt: take the stricter reading, log it), all written into
  p2/PREREGISTRATION.md: (1) home_adv is the fixed main-data value on F too, never re-estimated on fresh rows;
  (2) pre-2019 football-data files have no Time column, so data_pipeline's cleaning would drop every F row; a
  league-season without a Time column gets datetime = Date at 00:00, everything else is cleaned exactly as
  data_pipeline; (3) the snapshot triple is avg_h/d/a (DEV missing share 0.34% from coverage counts only); on F
  files without avg_* the same concept, the Betbrain average bb_av_h/d/a, is used, else STOP; (4) c is a ratio of
  sums (goals over SoT, both sides) over matches dated strictly before the row's date; (5) the Bonferroni level is
  1 - 0.05/3 (98.33%, the wider reading of "98.3%"); (6) market-only is refitted on DEV+VAL with the stack at the
  freeze, and both are frozen even if S2 is rejected (descriptive Phase 6 only); (7) the closing benchmark on F is
  avg_ch if present, else Pinnacle closing, labelled; (8) run_filter takes home_adv as a third argument, like
  exp_model.run_filter, and raises on drift, season variance or league effects, which P2 does not use;
  (9) EXPECTED_TESTS is set once all P2 tests exist (before the Phase 4 gate, which may only fail on the branch);
  it is the final collected total and is checked again at Phase 7. Approved: n/a, prompt rule.
- 2026-10-26 P2 Phase 2 (fresh data, counts only; results/p2/data_audit.md): 40 of 40 league-seasons fetched
  (penaltyblog FootballData, 2014-2015 to 2018-2019), 13,720 rows, 0 dropped by cleaning; 2,744 burn-in rows
  (2014-2015) and 10,976 scored rows. All 40 files lack a Time column, so the pre-registered datetime = Date fallback
  applies to every F row. Snapshot triple on F: bb_av_h/d/a (no avg_* in any F file), 0 rows missing it; closing
  benchmark on F: Pinnacle closing (psch/pscd/psca; no avg_ch). SoT (hst, ast) absent in NLD, PRT and TUR 2014-2015
  to 2016-2017 (w = 0 for those rows by the pre-registered rule). No team in two leagues, no team with two matches on
  one day. Raw cache data/fixtures_pre2019.pkl (not committed). Approved: n/a, pre-registered rule.
- 2026-10-26 P2 code: p2_model.py (filter with the S1 shots term), p2_stack.py (S2), run_p2.py (all phases),
  tests/test_p2.py (14 tests, synthetic, no network). run_p2.py --check: p2_model with shots_w = 0 and P1 parameters
  reproduces exp_model.run_filter P1 on all 19,145 rows, max abs difference 0.0 (results/p2/check.md). pytest
  collects 78 (64 existing + 14), all pass; tools/gate.py EXPECTED_TESTS 64 -> 78 (the only gate change, made now
  because every P2 test exists and the Phase 4 gate may fail only on the branch). Approved: user, 2026-10-26
  (session prompt exception).
- 2026-10-26 P2 S0 ACCEPTED (widened grid on P1, 12 candidates): process_noise 0.0025, initial_var 0.15,
  cold_defence 0.45 (process_noise and initial_var at the grid corner). DEV log-loss 0.997085 -> 0.989816, VAL
  0.981172 -> 0.973652, DEV+VAL diff -0.007352, 99% CI [-0.009042, -0.005788] (seed 20261030). Incumbent DEV/VAL
  equal E5's chosen values. Selection-period, retrospective. Not re-run. Approved: n/a, pre-registered rule.
- 2026-10-26 P2 S1 ACCEPTED (shots on target in the update, w in {0.25, 0.5, 0.75}): w 0.5 on top of S0. DEV
  log-loss 0.989816 -> 0.981546, VAL 0.973652 -> 0.968042, DEV+VAL diff -0.007396, 99% CI [-0.009959, -0.004874]
  (seed 20261030). Rows updated with shots (coverage, not a score): 99.67% of DEV, 99.95% of VAL. Selection-period,
  retrospective. Not re-run. Approved: n/a, pre-registered rule.
- 2026-10-26 P2 S2 REJECTED (stack of the S0+S1 goals-only model with the avg_h/d/a snapshot market, fitted on
  8,739 DEV rows with snapshot odds; 30 DEV rows lack them). DEV fit: stack a -0.062544, b 1.169269; market-only
  b 1.114231. Stack vs market-only log-loss DEV 0.969109 vs 0.969143, VAL 0.944966 vs 0.945214; DEV+VAL diff
  -0.000104 (n=13,030), 99% CI [-0.000296, +0.000072]: upper bound not below 0. T-C will not run. Selection-period,
  retrospective. Not re-run. Approved: n/a, pre-registered rule.
- 2026-10-26 P2 Phase 4 freeze (results/p2/candidate_p2.json, sha256 bf7d5226...e3f of the canonical JSON with the
  hash field blank): goals-only candidate = P1 + S0 + S1 (process_noise 0.0025, initial_var 0.15, cold_defence 0.45,
  clip_rates on, rho -0.04, shots_w 0.5); stack (a -0.125738, b 1.276749) and market-only (b 1.164921) refitted on
  13,030 DEV+VAL snapshot rows, frozen for the descriptive Phase 6 only because S2 was rejected. Fresh tests to run:
  T-A and T-B (T-C not run, S2 rejected). Approved: n/a, pre-registered rule.
- 2026-10-26 P2 Phase 5, FRESH out-of-time (2015-16 to 2018-19), first scoring of the frozen candidates (10,976 F
  rows; 98.3% paired week-block CI, seed 20261030; results/p2/fresh_once.md). T-A P1 minus Stage 2 baseline
  -0.013985, CI [-0.016001, -0.012097]: PASS. T-B goals-only candidate minus P1 -0.013857, CI [-0.017536,
  -0.010341]: PASS. T-C not run (S2 rejected). Ran once, no error, no rerun. Approved: n/a, pre-registered rule.
- 2026-10-26 P2 Phase 6, DESCRIPTIVE look at TEST_INDEX (TEST is not fresh; no claim from this; written after
  results/p2/fresh_once.md; results/p2/test_descriptive.md). Log-loss on 3,829 rows: baseline 1.008321, P1 0.995493
  (P1 minus baseline -0.012828, as the earlier P1 TEST result), goals-only candidate 0.980044, stack 0.961080,
  market-only (snapshot) 0.961423, closing average 0.961623. No parameter or rule changed. Approved: n/a,
  pre-registered rule.
- 2026-10-26 P2 Phase 7: results/FINDINGS.md section 9 added (45 numbers, each registered in results/claims.json as
  p2_001 to p2_045, appended); CLAUDE.md gains an appended P2 section. Disclosures: (1) results/p2/fresh_once.md also
  shows the frozen stack and market-only on F as descriptive rows (not pre-registered as Phase 5 output, no test,
  no verdict; T-C was not run); (2) its per-season and per-league differences carry 98.3% CIs, descriptive only, with
  no per-group verdict. EXPECTED_TESTS stays 78 (pytest collects 78). Approved: n/a, recorded.
- 2026-10-27 Live 2026-27 session (branch live2627). Exceptions granted by the session prompt: create live2627.py,
  tests/test_live2627.py, live2627/PREREGISTRATION.md, results/live2627/*.md and *.json; DECISIONS.md and CLAUDE.md
  append-only; results/claims.json entries appended only; results/FINDINGS.md gains a new section 10 only;
  tools/ownership.txt gains exactly those new paths; tools/gate.py changes only EXPECTED_TESTS; .claude/settings.json
  gains only the commit-trailer setting at the end. exp_model.py, p2_model.py, p2_stack.py, stage*.py, metrics.py,
  exp_harness.py, forward_logger.py, run_p2.py, forward/, p2/ and every frozen JSON are not edited. Commit messages
  carry no Co-Authored-By or Claude trailer (user instruction). Approved: user, 2026-10-27 (session prompt).
- 2026-10-27 Live preflight: branch live2627, clean tree, HEAD 4233f37 (descends from 4233f37); pandas 3.0.6, numpy
  2.5.4, scipy 1.18.1, statsmodels 0.15.0, penaltyblog 1.12.3 (rapidfuzz 3.14.6, pytest 9.1.1); python -X utf8
  main.py: 0.2057 / 0.2060 / 0.2059 / CHANGE_SCALE 0; the frozen JSONs load (P1 params check and P2 self-hash pass),
  sha256 recorded in live2627/PREREGISTRATION.md; home_adv from the first 15,316 rows of cleaned, stably sorted H
  equals 0.20356233139056304 (difference 0.0); full gate: only the branch check fails (expects main), 78 tests pass.
  Approved: n/a, recorded.
- 2026-10-27 Live readings taken before any 2026-27 fetch (prompt: take the stricter reading, log it), all written
  into live2627/PREREGISTRATION.md: (1) "the three frozen JSONs": M0 has no file, so candidate_p1.json,
  candidate_p2.json and the two incumbent.json files that pin the same parameters are hashed, as git blobs and as
  CRLF working copies (core.autocrlf is true); (2) data_pipeline's sort_values('date') is not stable: 7,748 H
  positions differ from a stable sort, all within equal timestamps, and the two 2025-02-01 13:00 matches swap sides of
  the 15,316 boundary; the TEST flag therefore follows data_pipeline's actual split (H is data_pipeline's frame) and
  home_adv is asserted on both orders; (3) the name audit flags a newcomer if the raw or the default_process WRatio is
  88 or more; (4) a duplicate row or pair, or a team twice on one day, is a STOP (no de-duplication rule exists);
  (5) the match bootstrap draws one index matrix used for both tests, quantiles 1.25% and 98.75%; SE = sd (ddof 1)
  over sqrt(n); (6) M3 probabilities are renormalized only if they miss 1 by more than 1e-10; (7) the forward log must
  pass forward_logger.verify_log, else STOP; (8) the scoring guard also requires the snapshot file to be committed, so
  --refresh is two-step (fetch and write; commit; the next --refresh scores); (9) a --snapshot mode runs Phase 2;
  (10) every scoring run also checks M0 against stage2_dynamic.run_sequential_filter; (11) a commit "live: scoring
  code and tests" precedes the primary scoring so that primary.md is produced by committed code (not in the prompt's
  commit list); (12) primary.json lists the scored rows with their forecasts so --verify can check that no TEST row
  was scored. Approved: n/a, prompt rule.
- 2026-10-27 Live Phase 2 BLOCKED (environment, not data). `python -X utf8 live2627.py --snapshot` stopped before any
  row was received: every request to www.football-data.co.uk is reset during the TLS handshake (WinError 10054) from
  both the Bash and the PowerShell tools of this session, while github.com is reachable, so the session's network
  sandbox does not allow the source. 3 attempts for ENG Premier League, then the pre-registered fetch STOP; nothing
  written (no results/live2627/ files). One rerun with the sandbox lifted was denied by the permission system and was
  not worked around. No 2026-27 row has been seen by this session. Approved: n/a, disclosure.
- 2026-10-27 Live order change caused by the block: Phase 3 (live2627.py complete, tests/test_live2627.py with 13
  tests, all passing; tools/gate.py EXPECTED_TESTS 78 -> 91, the pytest collected total) is committed as "live:
  scoring code and tests" before the Phase 2 snapshot, so the snapshot and scoring code are fixed before any 2026-27
  data is seen. Synthetic dry run in a temporary repository (no real L data): both equality checks 0.0, the guard
  refused uncommitted snapshot files, --verify passed. Phases 2, 4 and 5 (snapshot commit, primary scoring, FINDINGS
  section 10 and claims) are not done. Approved: n/a, prompt rule (stricter reading: code before data).
- 2026-10-27 Trailer: Claude Code settings reference (code.claude.com/docs/en/settings-reference, read 2026-10-27):
  `attribution.commit` set to an empty string hides commit attribution; `includeCoAuthoredBy` is deprecated since
  v2.0.62; `attribution: false` needs v2.1.281 or later. Merged `"attribution": {"commit": ""}` at the end of
  .claude/settings.json; nothing else in the file changed. Approved: user, 2026-10-27 (session prompt).
- 2026-10-27 Live Phase 2 snapshot: results/live2627/snapshot_20261026.json and manifest_20261026.json were present,
  uncommitted, at the start of this session (fetched_at_utc 2026-10-26T19:38:02Z, code commit ee9f64d, code_dirty
  false; 571 rows fetched, 571 completed; rows sha256 57df218f...6294). Not re-fetched; --snapshot not run again.
  These two files are the only 2026-27 data used. Approved: user, 2026-10-27 (session prompt).
- 2026-10-27 Live POST-HOC STRICTER READING of the name audit (club_id alias check), decided after the snapshot and
  before any score. The pre-registered rule (best same-league WRatio, raw or default_process, >= 88) flagged 0 of 11
  newcomers and missed a known alias. Check: for each newcomer, top 3 H names across all leagues by WRatio (raw and
  processed); H names get their Transfermarkt club_id from lineup.link_fixtures (unchanged; one club_id per H name);
  the newcomer's own club_id(s) are the clubs in data/clubs.csv.gz (name, club_code) or data/games.csv.gz (club names)
  whose name contains the newcomer's folded name; an alias is a newcomer club_id that appears in H under another name.
  Result: 1 alias. Erzurumspor (L, TUR Super Lig) = club 39722 "Erzurumspor FK", club_code
  buyuksehir-belediye-erzurumspor, which is H's "Erzurum BB" (TUR 2020-2021, all 40 H rows link to 39722); its best
  same-league WRatio was 66.7 (Bodrumspor), so the WRatio rule did not catch it. No other alias: Coventry 990, Hull
  3008 (also 12335 Solihull Moors), La Coruna 897, Malaga 1084, Santander 630 (also 103271), Elversberg 64, Academico
  Viseu 7788 do not appear in H; Le Mans, Amedspor and Corum have no club_id in the tables (not decidable by club_id,
  not flagged). Action: Erzurumspor is flagged (live2627.CLUB_ID_ALIASES) and its 8 L rows (all TUR Super Lig) are
  excluded from the primary test set; no names are merged in any data; T1/T2, the rule and the other exclusions are
  unchanged. Evidence table in results/live2627/data_audit.md; reproduce with live2627.py --alias-check. New test:
  a club_id-flagged team is excluded with WRatio below 88; tools/gate.py EXPECTED_TESTS 91 -> 92 (pytest total).
  Approved: user, 2026-10-27 (session prompt).
- 2026-10-27 Live Phase 4 PRIMARY scoring of snapshot 1 (results/live2627/primary.md and primary.json; code commit
  a360eef, clean), run once, no error, no rerun. Equality checks 0.0 and 0.0 over 19,716 concatenated rows; no string
  cast. Test set 563 (571 completed; 0 forward-log rows; 8 Erzurumspor rows excluded as a club_id alias, post-hoc
  stricter reading above). T1 M1 minus M0 -0.014830, 97.5% CI [-0.027430, -0.003056]: ACCEPTED. T2 M2 minus M1
  -0.014795, 97.5% CI [-0.030241, -0.000024]: ACCEPTED (upper bound 2.4e-5 below 0). Retrospective forecasts, not
  timestamped before kickoff. live2627.py --verify: PASS. Approved: n/a, pre-registered rule.
- 2026-10-26 Post-hoc approved exception: presentation session gate scope, two changes. (1) tools/ownership.txt gains
  presentation/*. (2) tools/verify_claims.py also scans presentation/outline.md (every number must appear in
  results/FINDINGS.md or equal a claims.json value; source tags like [2, 6] and 16:9 are ignored) and the PLOTTED dict
  of presentation/make_figures.py (each value must equal a claim value); both are skipped when the file is absent.
  No other check, constant, anchor or claim changed; claims.json and FINDINGS.md untouched. The outline no longer
  states a forward-log count, because no claim backs one. Comparison of every plotted value with FINDINGS: no
  mismatch. The new test is an extra case inside test_uncovered_number_fails, so EXPECTED_TESTS stays 64. Approved:
  user, 2026-10-26.
- 2026-10-28 Fan-features session (branch demo). Exceptions granted by the session prompt: create fan_features.py,
  tests/test_fan.py, fan/NOTES.md, results/fan/*.md and results/fan/*.json; DECISIONS.md append-only;
  tools/ownership.txt gains exactly those five paths; tools/gate.py changes only EXPECTED_TESTS, to the final pytest
  total. FINDINGS.md, README.md, claims.json, every model file, forward/, p2/, live2627/ and every frozen JSON are not
  edited; their helpers are imported. Commit messages carry no Co-Authored-By or Claude trailer. Approved: user,
  2026-10-28 (session prompt).
- 2026-10-28 Fan preflight: branch demo, clean tree, HEAD a2d7337; pandas 3.0.6, numpy 2.5.4, scipy 1.18.1,
  statsmodels 0.15.0, penaltyblog 1.12.3; python -X utf8 main.py: 0.2057 / 0.2060 / 0.2059 / CHANGE_SCALE 0;
  python -m pytest -q: 92 passed (= EXPECTED_TESTS); candidate_p2.json loads; snapshot_20261026.json rows sha256
  equals its manifest (live2627.snapshot_failures: none). Approved: n/a, recorded.
- 2026-10-28 Fan readings (prompt: take the stricter reading, log it): (1) README.md does not exist at the root; the
  other four binding files were read and nothing was created in its place. (2) exp_model.dixon_coles_probs takes
  max_goals but returns only 1X2, not the grid, so the market grid is a thin reimplementation, tested against it to
  1e-12 at max_goals 10 and 30. (3) "Pre-normalisation mass" is the mass of the uncorrected Poisson product grid at
  30 goals, before the rho factors; below 1 - 1e-7 raises. (4) Final team states are the objects p2_model.run_filter
  passes to update_step, recorded by patching p2_model.update_step as forward_logger.snapshot_states does for
  exp_model (that function is exp_model-specific, so the pattern is reused, not the function); a final state is
  post-update with no extra predict_step; the wrapped run's forecasts must equal an unwrapped run's exactly. (5) VAL is
  exp_harness.split_index's val on H only (non-TEST H rows from 2023-07-01); L rows are not added to VAL. (6) Every
  95% half-width is the normal approximation: 1.96 sqrt(p(1-p)/n) for rates, 1.96 sd/sqrt(n) for means and mean
  score differences. (7) Climatology is the over-2.5 and BTTS base rate over H rows dated before 2020-07-01 (all
  non-TEST, asserted). (8) The 1X2 grid diagnostic covers the scored rows only (live test set and VAL). (9) Per team,
  matches before 2026-27 (H, the cached history, counts only) and in 2026-27 (L) are both stored, with their sum.
  (10) Top-scoreline ties sort by probability descending, then home goals, then away goals. (11) Ranks: 1 is best;
  attack by highest factor, defence by lowest factor, overall by highest attack/defence ratio. (12) Rating teams are
  the active 2026-27 teams of each league minus the teams flagged by live2627.name_audit; the filter itself still
  runs over every row, flagged teams included. (13) The sd-versus-matches rank correlation uses established teams,
  total matches, attack and defence sd separately (Spearman). Approved: n/a, prompt rule.
- 2026-10-28 Fan correction session (branch demo, on top of 695d4e1). Prompt rules taken: no scoring or editing of TEST,
  results/experiments/test_once.md, results/p2/, results/live2627/, forward/predictions.jsonl or any PREREGISTRATION.md;
  no anchor or committed results JSON changes; no attribution lines in commits; no push, PR or force-push.
  Edited or created: fan_features.py, tests/test_fan.py, tests/test_fan_independent.py, fan/NOTES.md (appended),
  fan/FINAL_REPORT.md, fan/GATE_RESULT.txt, results/fan/*.json and *.md, results/FINDINGS.md (a new section 11 only),
  results/claims.json (14 entries appended, each with an extra "script" field the verifier ignores), tools/ownership.txt
  (fan/FINAL_REPORT.md, fan/GATE_RESULT.txt, tests/test_fan_independent.py), tools/gate.py (EXPECTED_TESTS only, to the
  collected total). Approved: user, 2026-10-28 (session prompt) for the claims, ratings and test work. Two choices were
  taken by default and are flagged for review: (a) FINDINGS section 11, because tools/verify_claims.py accepts a claim
  only if its value appears in results/FINDINGS.md, so item 3 (claims that pass the verifier) cannot be met otherwise;
  the earlier fan prompt's ban on editing FINDINGS was scoped to that session; (b) EXPECTED_TESTS, covered by the earlier
  fan prompt's exception for the final collected total.
- 2026-10-28 DIAGNOSIS of ratings check 4 (/diagnose, read-only, outputs/diagnose/fan_sd.py and fan_sd.txt). Result: the
  expectation that defence sd falls with matches played did not hold (defence Spearman +0.456, attack -0.396, n = 139
  established teams). Class (d), spec problem: the expectation was badly chosen. Evidence: a plain-loop variance
  recursion from the model's per-row rates matches the captured states exactly (max difference 0.0); the placebo
  (matches shuffled within league, 200 draws, seed 20261019) gave 0 of 200 as extreme as the observed defence value.
  No verdict, spec or expected number changes. Approved: n/a, pre-registered rule (report; no change to the spec).
- 2026-10-28 POST-HOC EXPLORATORY – not pre-registered – not for deliverables: partial correlations, goal rate held
  fixed: defence -0.09, attack -0.04 (Spearman of matches with sd after removing the last-20-match mean modelled
  conceded or scoring rate, n = 139). Mechanism figures from the same exploration: Spearman of matches with the mean
  modelled conceded rate -0.48, and of that rate with the defence sd -0.98. These are not in claims.json, FINDINGS,
  ratings_check.md or any fan page. One post-hoc look only; no further runs. Approved: n/a, recorded.
- 2026-10-28 Wording changes. (1) The reading of check 4 now says, in order, that the expectation did not hold, that
  defence sd rises (Spearman +0.456) while attack sd falls (Spearman -0.396), and n = 139 established teams; n is beside
  every statistic. It is generated from the computed values (fan_features.reading_sentence) and a test checks that
  ratings_check.md and fan/NOTES.md contain it. The earlier mechanism sentence was removed because it rested on the
  post-hoc exploration. (2) "Not an underpowered null" appears in no committed file (it was only in the diagnosis
  message) and a test forbids "underpowered" in ratings_check.md. The smallest |rho| is stated as about 0.17 at n = 139
  established teams; it is the usual two-sided significance threshold, 1.96 / sqrt(n - 1), not an 80% power figure, and
  the text says so. (3) The phrase "independent recomputation" appears in no committed fan file. Earlier entries in this
  log use "independent" for other sessions' checks; they are append-only and unchanged.
- 2026-10-28 Gap: fan/NOTES.md had no update equations, so the plain-loop check could not be written from it. They were
  added to NOTES.md (written from stage2_dynamic.py by the same author as the code and the test) and
  tests/test_fan_independent.py was written from them without importing fan_features.py. It takes lambda and mu per
  match from the model's own output, so it checks variance bookkeeping and state capture (max difference below 1e-9
  against the committed ratings), not the rates. Because the equations and the test share an author, the check is NOT
  described as independent anywhere; the file name is the one the prompt required. Approved: n/a, stricter reading.
- 2026-10-28 Simulation (fan_features.simulate_matches, seed 20261028 pinned in code, results/fan/ratings_sim.json):
  eight synthetic leagues of 20 teams over seven seasons, true strengths from the model's own prior (initial_var), the
  model's random-walk step (process_noise) at each appearance, the model's cold-start prior for later entrants, goals
  Poisson with the model's clipped rates; the three weakest teams by points then goal difference leave each season.
  The league, team, season and exit counts are design constants, not fitted. Same frozen filter code, no real data.
  Result: defence +0.236, attack -0.130 (n = 136): the signs match the real teams. The design has two things that can
  produce the shape (filter variance dynamics, and strong teams staying longer); one simulation cannot separate them,
  and a random-exit variant was not run (the prompt asked for one simulation). The text says "what the model implies",
  not a football finding. The defence-bar note the prompt prescribes ("a property of the model, not of the team") is
  therefore supported only to that extent; it is kept as prescribed and the limit is in FINAL_REPORT.md.
  Approved: n/a, pre-registered default.
- 2026-10-28 Labels and the fan page: the page does not exist and the prompt forbids starting the dashboard, so the label
  "model uncertainty, not measured accuracy" (on every team record) and the defence-bar note (on every league) are data
  fields in results/fan/ratings.json, also printed in ratings_check.md, with a test. Page text is not built or tested.
- 2026-10-28 Claims scope. Every number in results/fan/ratings_check.md, fan/FINAL_REPORT.md and FINDINGS section 11
  is a value in claims.json; tests/test_fan.py checks the first two and tools/verify_claims.py checks FINDINGS. The
  per-team factors, sds and per-league values that used to be tables in ratings_check.md now live only in
  ratings.json (a data file). NOT covered, open: results/fan/markets_calibration.md (committed before this rule) and
  fan/NOTES.md contain numbers with no claim, and the JSON data files are not claim-checked. Verifier unchanged.
- 2026-10-28 Byte-identity test (item 9): the committed metric files results/fan/markets_calibration.json,
  results/live2627/primary.json and results/p2/S0.json, S1.json, S2.json are hashed (sha256 of the LF-normalised bytes)
  against pins taken from base commit 695d4e1. They are hashed as opaque bytes, never parsed or scored.
  results/p2/test_descriptive.json (TEST) is not touched. Experiment JSONs under results/experiments do not hold
  RPS, LogLoss or Brier under those key names and are not pinned.
- 2026-10-28 fan_features.py --markets no longer rewrites committed files: it recomputes the payload and requires it to
  equal the committed markets_calibration.json apart from the provenance block (it did, exactly), then leaves the
  files unchanged. This keeps item 9 true on every rerun. The Phase 4 outputs and tests/test_fan.py from the first fan
  prompt, not yet written at the start of this session, were completed here: results/fan/model_constants.json,
  results/fan/sample_forecasts.json and the listed tests. README.md does not exist and was not created.
- 2026-10-28 Step 1 (close gaps on demo before merging; second fan correction prompt). Approved: user, 2026-10-28
  (session prompt). (a) Unclaimed numbers found with tools/verify_claims.numbers_in against claims.json: 182 distinct
  in results/fan/markets_calibration.md, 11 in fan/NOTES.md, 0 in ratings_check.md, FINAL_REPORT.md and the other
  results/fan/*.md. Policy: prefer deletion. DELETED from markets_calibration.md: every table value (Brier, log-loss,
  skill, rates, half-widths, reliability bins and counts, scoreline hit rates, climatology rates and n, grid-diagnostic
  maxima, the row counts). The report now states the comparisons in words computed from the committed JSON (a gap
  inside or outside its own interval); all values remain in markets_calibration.json, which is unchanged byte for byte.
  The 182 distinct deleted tokens were:
    -0.0300 -0.0143 -0.0134 -0.0090 -0.0066 -0.0043 -0.0009 -0.0004 0.0000 00 0.0006 0.0014 0.0016 0.0017 0.0024
    0.0033 0.0034 0.0040 0.0049 0.0068 0.0069 0.0070 0.0088 0.0093 0.01 0.0101 0.0140 0.0141 0.0149 0.0177 0.0188
    0.0226 0.0243 0.0262 0.0268 0.0272 0.0298 0.0307 0.0326 0.0367 0.0401 0.0407 0.0456 0.0485 0.0589 0.0611 0.0686
    0.0700 0.0723 0.0777 0.0883 0.0893 0.0959 0.1 0.1036 0.1162 0.1198 0.1213 0.1279 0.1326 0.1479 0.1519 0.1822
    0.1886 0.2 0.2000 0.2279 0.2285 0.2407 0.2410 0.2428 0.2450 0.2468 0.2472 0.2476 0.2691 0.2718 0.2750 0.2865
    0.3085 0.3185 0.3279 0.3333 0.3506 0.3563 0.3627 0.3721 0.3757 0.4 0.4390 0.4486 0.4535 0.4552 0.4598 0.4602
    0.4730 0.4853 0.5166 0.5333 0.5334 0.5346 0.5348 0.5399 0.5413 0.5485 0.5492 0.5497 0.5512 0.5516 0.5522 0.5537
    0.5544 0.5604 0.5614 0.5826 0.5927 0.6 0.6129 0.6147 0.6200 0.6217 0.6268 0.6380 0.6390 0.6434 0.6467 0.6487
    0.6625 0.6667 0.6742 0.6750 0.6787 0.6831 0.6868 0.6876 0.6884 0.7 0.7013 0.7182 0.7233 0.7242 0.7321 0.7393
    0.7500 0.7619 0.8 0.8049 0.8182 0.8252 0.8348 0.9 0.9108 1.0 2.5 3 04 5 21 24 30 39 41 44 80 120 122 150 154 186
    204 248 330 457 844 968 1076 1297 1377 1865 2,256 4291 19,716
  DELETED or reworded in NOTES.md (11): 0.20356233139056304 (home_adv, now referred to by name), 30 (now
  fan_features.MARKET_GOALS), 12 (the test tolerance, now unnamed), 19,716 (the concatenated row count), 100% and
  99.83% (shots-on-target completeness, now in words), and the step numbers 2 to 6 (the update equations are now
  labelled (a) to (g); tests/test_fan_independent.py comments follow). KEPT with a new claim: one number, 2.5, because
  the over market is named over 2.5 and a dashboard needs it: claims.json fan_over_line (source
  results/fan/model_constants.json, script fan_features.py --outputs), one bullet appended to FINDINGS section 11.
  fan_features.markets_text was rewritten to produce the number-free report; keep_committed now rewrites only that
  report from the committed JSON. tests/test_fan.py now checks every .md in results/fan and fan against claims.json.
  (b) The defence note is now: "Defence bars do not narrow with more matches. This most likely reflects how the model's
  variance behaves. A simulation reproduced the signs but could not separate this from team selection, so treat it as
  unconfirmed (see ratings_check.md)." in fan_features.DEFENCE_BAR_NOTE, results/fan/ratings.json (top level and every
  league), ratings_check.md, NOTES.md and FINAL_REPORT.md; the field test asserts it and forbids the old phrase.
  ratings.json, ratings_sim.json, model_constants.json and sample_forecasts.json were regenerated; apart from the
  provenance block and the note they are identical to the committed versions (checked field by field), so no number
  moved. The earlier DECISIONS entries that quote the old note are append-only and stand as history.
  (c) git ls-tree main README.md: empty; demo has none either. Nothing created. (d) git diff main -- tools/gate.py: only
  EXPECTED_TESTS differs (92 on main, 123 on demo); nothing to revert. (e) python -m pytest -q on demo: 123 passed; git
  status afterwards showed none of TEST, results/experiments/test_once.md, results/p2/, results/live2627/,
  forward/predictions.jsonl or any PREREGISTRATION.md changed.

   ## 2026-10-28 - Reproduction check of results/fan/ratings.json
   Re-ran `python fan_features.py --ratings` in a copy of the repo (C:\dev\b12-check, outside the tracked tree). Every top-level key of the output equals the committed results/fan/ratings.json except `provenance`. The committed file was recorded with fan_features_dirty: true. The discrepancy is in provenance metadata only; no numbers differ. No file in results/fan/ was edited.

## 2026-10-29 - Newcomer definition stated in results/fan/ratings_check.md
results/fan/ratings_check.md used "newcomer" without defining it. One sentence was added under section 3, quoting the
rule in fan_features.league_ratings (`newcomer=history_n == 0`, history_n = the team's home and away appearances in
the history frame H from live2627.load_history); every other listed team is an established team. No number changed.
The sentence was added to the committed markdown only: fan_features.py was not edited (its sha256 already differs from
the recorded provenance, see the entry above), so a regeneration of ratings_check.md would drop the sentence. Commit
a117abd "fan: state newcomer definition". pytest 123 passed; gate on pp: only the branch check failed. Decided by
the assistant under the user's task prompt (Step 1).

## 2026-10-29 - PP (plan item 3) pre-registered
pp/PREREGISTRATION.md committed in 8392c3fff8d6fc25cf9c3ec612359393167d3bda ("pp: preregistration") before
pp_model.py existed and before any PP forecast was computed. sha256 of the committed file:
9d24e82b97a972bb99a4ce96197c609123ed565fbd5aa962b53f1918dbebcd51.
Deviation from the task prompt, as the prompt itself directs: the prompt proposed RPS as the primary metric and said
the P2 rule wins where the two differ. The P2 selection rule decides on log-loss with a 99% paired week-block CI, so
PP is decided on log-loss under that rule (DEV and VAL log-loss improve, and the 99% CI upper bound on DEV+VAL is below
0); RPS and Brier are reported, not decisive. The S2 restriction to rows with snapshot odds does not apply because PP
does not use the market. tools/ownership.txt gained this work's own new files (pp/, pp_model.py, run_pp.py,
tests/test_pp.py, results/pp/, HANDOFF.md). Decided by the assistant under the user's task prompt (Step 3).

## 2026-10-29 - PP v1: a failed pre-registered check; v1 evaluation never run
pp/PREREGISTRATION.md (v1, commit 8392c3f) required check (c): 9 and 21 Gauss-Hermite nodes agree to 1e-6 on 50 real
matches. It failed: the largest difference in the home/draw/away probabilities was 6.69e-05, and 24% of the 50 rows
exceeded 1e-6. As v1 requires, the evaluation did not run: no DEV/VAL outcome was computed. The v1 pp_model.py and
tests/test_pp.py were never committed. v1 stays committed and unchanged.
Post-failure diagnosis (outputs/diagnose/pp_nodes_check.py, outcome-free, not committed): an independent
implementation (own Poisson pmf, Dixon-Coles, normalisation and quadrature) matched pp_model to at most 4.4e-16 on
2,000 non-TEST rows (seed 20261019). With the rate clip off, 9 and 21 nodes agreed to at most 3.0e-07 on the 50 rows.
On the 2,000 rows, 58% have at least one 9-node rate outside the clip bounds; their median 9-vs-21 difference was
2.2e-07, against at most 3.2e-08 on rows with no clipped node. On the 50 rows, 21 nodes differed from a 301-point
trapezoid reference by up to 1.35e-05. The largest change in per-row log-probability between 9 and 21 nodes was
3.1e-04 (50 rows) and 3.0e-03 (2,000 rows). Reading of the diagnosis: the rate clip makes the integrand non-smooth, so
the quadrature converges slowly where a node is clipped. This is a post-failure diagnosis, not a pre-registered
finding. The owner (the user) instructed a v2 pre-registration on 2026-10-29, replacing the assistant's recommendation
to record item 3 as not run.

## 2026-10-29 - PP v2 pre-registered (owner instruction)
pp/PREREGISTRATION_v2.md committed in 0dd45c34eff9240dc47166b79444380fdb79c137 ("pp: preregistration v2") before any
DEV/VAL outcome was computed for PP and before N* was selected. sha256 of the committed file:
12bf26792d73fc5cf93323d38d181f5095643b1fc624c1e8235b0757e9f33fe2. New outcome-free node rule: N* = smallest of 9, 21,
41, 81, 161, 301 within 1e-5 of the 301-node reference on the 2,000 diagnostic rows. Approved by: the owner (the user),
instruction of 2026-10-29.
Decision rule: the owner's instruction says "copied unchanged from v1 and the P2 S2 rule" and describes it as RPS. v1
decides on log-loss (the P2 rule), so the two parts of the instruction conflict. Default taken: the rule stays
unchanged from v1 (log-loss, 99% paired week-block CI, DEV and VAL each improve). Changing the decisive metric after a
failed check would change a locked rule. RPS with its 99% CI is reported, not decisive. Decided by the assistant under
the owner's "do not ask" instruction; the owner may overrule this before the evaluation runs.

## 2026-10-29 - PP v2: N* selected without outcomes
`python -X utf8 run_pp.py --select-nodes` (code commit 14592ff) wrote results/pp/pp_nodes.json. Largest absolute
difference from the 301-node reference over every scoreline cell and home/draw/away on the 2,000 fixed rows: 9 nodes
5.35e-04, 21 nodes 2.77e-04, 41 nodes 1.74e-04, 81 nodes 5.36e-05, 161 nodes 4.39e-05. None is below 1e-5, so the
pre-registered fallback applies: N* = 301. Its recorded maximum error is 0 only because it is the reference itself; the
rule does not measure the error of the 301-node integration against the exact integral, and the slow decrease along
the ladder (the rate clip makes the integrand non-smooth) means that error is not shown to be below 1e-5. No outcome was
used. Pre-registered rule applied as written; no approval needed.

## 2026-10-29 - PP v2 outcome: REJECTED (v2, revised after a failed numerical check)
`python -X utf8 run_pp.py --evaluate` ran once (no crash, no re-run) and wrote results/pp/pp_dev_val.json and
results/pp/pp_decision.md (commit 0f6a768). PP with N* = 301 against the frozen P2 goals-only candidate on DEV+VAL
(13,060 rows): log-loss worse on DEV (0.981546 to 0.983277) and on VAL (0.968042 to 0.971352); 99% paired week-block
CI of the per-row log-loss difference [+0.001561, +0.003001]. All three checks failed: REJECTED. RPS (reported, not
decisive) is also worse, 99% CI [+0.000253, +0.000491], so the log-loss versus RPS conflict in the v2 instruction does
not change the outcome. The 2009-14 confirmation was not run, and those seasons stay untouched. FINDINGS section 12
and claims pp_001 to pp_015 record it. Labelling: the result carries the owner's label "v2, revised after a failed
numerical check". It is not labelled EXPLORATORY because v2, including the node rule, was committed before any
outcome for this forecast was computed; the revision is disclosed in FINDINGS section 12. Item 3 is closed as a
negative finding. Nothing in results/fan/, results/p2/, results/experiments/, results/live2627/ or forward/ changed.