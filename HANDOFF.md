# HANDOFF (B12 football match prediction)

Written 2026-10-29 on branch pp. Statistics live in `results/FINDINGS.md`, every number backed by
`results/claims.json`. This file holds pointers only. CLAUDE.md holds the binding rules; where they differ, it wins.

## What the project is
A sequential Bayesian model for football results: each team's attack and defence are Gaussian states updated after
every match (Poisson rates, Dixon-Coles low-score correction). The two mid-semester novelties (surprise-driven updates
and lineup weighting) failed under pre-registered tests. Everything since then is a pre-registered, gated pipeline:
learned parameters (P1), improvements tested on fresh seasons (P2), a retrospective look at live 2026-27 matches, a
hash-chained forward logger, and fan-facing outputs (scoreline markets, ratings with model uncertainty).

## Where things live
- Branches: main (b1f30ce at handoff, on origin); pp (this work, ahead of main, not merged); merged or historical:
  demo, experiments, forward-logger, gate-b-lineup, live2627, p2, presentation.
- Tags: gate-a-passed (f689a4c), results-frozen-2026-10-26 (3294349), consolidated-2026-10-27 (a2d7337),
  fan-features-v1 (616f831).
- Key commits on pp: a117abd newcomer definition; 8392c3f PP v1 pre-registration; b876aee v1 failed-check record;
  0dd45c3 PP v2 pre-registration; 14592ff PP code and tests; 2a48ca6 node selection; 0f6a768 evaluation;
  58605db FINDINGS section 12.
- Code: data_pipeline.py, stage1_baseline.py, stage2_dynamic.py, stage3_detector.py, metrics.py (frozen stages);
  exp_model.py, exp_harness.py, run_experiments.py (P1); p2_data.py, p2_model.py, p2_stack.py, run_p2.py (P2);
  live2627.py; forward_logger.py; fan_features.py; pp_model.py, run_pp.py (posterior-predictive item).
- Frozen candidates: results/experiments/candidate_p1.json, results/p2/candidate_p2.json (self-hashed).
- Pre-registrations: p2/, live2627/, forward/, pp/ (v1 and v2). Never edit a committed one.
- Results: results/FINDINGS.md (sections 1 to 12), results/experiments/, results/p2/, results/live2627/,
  results/fan/, results/pp/. Decisions log: DECISIONS.md (append-only, dated).
- Presentation material: presentation/outline.md, presentation/make_figures.py, presentation/figures/.
- Local only, never committed: data/ (fixture cache, Transfermarkt tables), outputs/ (including outputs/diagnose),
  venv/. Never run git clean here.

## Protocol status (which data is spent)
- BURN-IN before 2020-07-01: filtered, never scored.
- DEV 2020-07-01 to 2023-06-30 and VAL from 2023-07-01 (TEST rows excluded by row identity): selection only, used
  by P1, P2 and the posterior-predictive item.
- TEST (Feb 2025 to May 2026): spent. Scored once for P1, then once more descriptively (FINDINGS sections 6 and 9).
  Never score it again.
- FRESH 2015-16 to 2018-19 (2014-15 burn-in): spent on the P2 replication (FINDINGS section 9).
- Live 2026-27 snapshot: spent on T1 and T2 (FINDINGS section 10). Later refreshes are descriptive.
- 2009-10 to 2013-14: untouched. The posterior-predictive item was rejected, so its confirmation never ran.
- Forward log (forward/predictions.jsonl): append-only, hash-chained; see FINDINGS section 8 for its status.

## Accepted versus rejected
- Accepted: P1 parameter choices E1, E3, E5 (section 5); P2 steps S0 and S1 (section 9); fresh tests T-A and T-B
  (section 9); live tests T1 and T2, T2 marginal (section 10); Gate A (section 1).
- Rejected or failed: surprise mechanism (section 3); lineup Gate B (section 4); P1 E2, E4, E6 (section 5); P2 stack
  S2 (section 9); posterior-predictive forecast (section 12).
- Descriptive only: TEST second look (section 9), fan ratings checks (section 11), live refresh reports.

## Item 3 outcome (posterior-predictive forecast)
REJECTED, labelled "v2, revised after a failed numerical check". v1 (pp/PREREGISTRATION.md) failed its own
pre-registered numerical check (9 vs 21 Gauss-Hermite nodes), so its evaluation never ran. On the owner's instruction,
v2 (pp/PREREGISTRATION_v2.md) was committed before any DEV/VAL outcome for this forecast. It kept the v1 decision rule
(log-loss, the P2 rule) and added an outcome-free node rule, which fell back to the 301-node reference. The evaluation
ran once and the forecast was worse on DEV and VAL. Details: FINDINGS section 12, results/pp/pp_decision.md, DECISIONS.md
(2026-10-29 entries). The fan outputs keep the plug-in forecast.

## Environment
- Windows, PowerShell, repo C:\dev\b12, venv C:\dev\b12\venv. After a terminal relaunch:
  `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` then `& C:\dev\b12\venv\Scripts\Activate.ps1`.
- Pinned: pandas 3.0.6, numpy 2.5.4, scipy 1.18.1, statsmodels 0.15.0, penaltyblog 1.12.3 (never upgrade it).
- Full test run takes about three minutes. One ConstantInputWarning from tests/test_fan.py is known and harmless.
  pytest.ini scopes collection to tests/; never collect split_test.py (it re-scores TEST).

## Gate
- `python -m pytest -q`, then `python -X utf8 tools\gate.py` (`--fast` skips the anchor run; commits only).
- On main it must print GATE: PASS. On any other branch exactly the branch check fails, and that is allowed.
- The anchors (Stage 1 / Stage 2 / all-rows RPS and CHANGE_SCALE 0) and the expected test count are in tools/gate.py.
  Never edit them, tools/ownership.txt or results/claims.json to make the gate pass without the owner's approval.

## Standing rules
- Never rebase, amend, squash or force-push: commit hashes are cited in pre-registrations and the forward log.
- The owner runs checkouts, merges, pushes and tags. An assistant commits on its branch only.
- Commit messages and git command lines must not contain the words the project deny rules match (the branch-changing,
  combining, publishing and history-rewriting git verbs); run git add and git commit as separate calls.
- No Co-Authored-By, "Generated with" or any attribution in commits or PRs (.claude/settings.json sets an empty
  commit attribution). Older commits keep their trailers until the deferred cleanup.
- Do not score or edit TEST, FRESH, live2627, forward/, committed pre-registrations, results/p2/,
  results/experiments/ or results/fan/. Frozen parameters and forecast code never change after the first forward log.
- Every number in a deliverable needs a FINDINGS entry and a claims.json entry; tools/verify_claims.py must pass.
- Tune and decide on DEV/VAL only. No post-match information in any feature. Outputs to outputs/, data to data/.
- Failure protocol (CLAUDE.md): stop, run /diagnose, classify, never change a locked rule without the owner's approval,
  log every deviation in DECISIONS.md, label post-hoc results EXPLORATORY.
- If a git command is denied, do not work around it; the owner runs it.

## Open items
1. Dashboard (one HTML page): upcoming forecasts from the best frozen model, track record, ratings with uncertainty
   bars labelled "model uncertainty, not measured accuracy", matchup tool, and a visible caveats panel. It reads
   results/fan/ and results/pp/ (only as a negative finding; the forecast stays plug-in). Numbers only from committed
   results.
2. Replication on 2009-10 to 2013-14 (untouched): optional; needs its own pre-registration.
3. Deferred co-author trailer cleanup in old commits: after the project, without rewriting cited hashes.
4. Forward logger upkeep: `python -X utf8 forward_logger.py --verify`; `--score` only after matches finish.
5. One-command refresh and a short demo script, after the dashboard.
6. ratings_check.md's newcomer sentence is in the committed markdown only; a regeneration by fan_features.py would
   drop it (DECISIONS.md, 2026-10-29).
