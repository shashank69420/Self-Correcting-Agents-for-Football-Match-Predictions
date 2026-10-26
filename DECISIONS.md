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
- 2026-10-26 Post-hoc approved exception: presentation session gate scope, two changes. (1) tools/ownership.txt gains
  presentation/*. (2) tools/verify_claims.py also scans presentation/outline.md (every number must appear in
  results/FINDINGS.md or equal a claims.json value; source tags like [2, 6] and 16:9 are ignored) and the PLOTTED dict
  of presentation/make_figures.py (each value must equal a claim value); both are skipped when the file is absent.
  No other check, constant, anchor or claim changed; claims.json and FINDINGS.md untouched. The outline no longer
  states a forward-log count, because no claim backs one. Comparison of every plotted value with FINDINGS: no
  mismatch. The new test is an extra case inside test_uncovered_number_fails, so EXPECTED_TESTS stays 64. Approved:
  user, 2026-10-26.
