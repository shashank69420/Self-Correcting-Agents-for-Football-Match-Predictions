# Live 2026-27 pre-registration

Written and committed on 2026-10-27 on branch live2627, code commit 4233f375391de7cd6082cb4a888620fea088d551, before
this session fetched any 2026-2027 data. Nothing in this file changes after the commit "live: preregistration".
Parameters, grids and rules below were fixed before L was fetched.

Allowed wording, used in every report: "Parameters were fixed before 2026-27 data was fetched. Forecasts were
recomputed after the matches were played and are not timestamped before kickoff. Team ratings update with each result
as it arrives."

## Purpose
Score models whose parameters were fixed on earlier seasons on completed 2026-27 league matches: pre-register, snapshot
the results, score once, and repeat descriptively as more matches are played. No model code and no frozen parameter
changes. No parameter of M0-M2 was set with any 2026-27 result: P1 was frozen on 2026-10-25 and P2 on 2026-10-26 from
DEV/VAL and the 2014-2019 seasons only (DECISIONS.md). The forward logger (a separate stream) read 2026-27 results as
history on 2026-10-26 and scored no match.

## Frames
- **H (history).** `data/fixtures_raw.pkl` cleaned by `data_pipeline.ingest_and_clean_fixtures(refresh=False)` (through
  `run_experiments.load_data`): drop rows missing goals_home, goals_away or datetime, `date = pd.to_datetime(datetime)`,
  `sort_values('date')`, `reset_index(drop=True)`; 19,145 rows, 2019-08-02 to 2026-05-24.
- **TEST flag.** Before any concatenation, the H rows in TEST_INDEX are flagged by row identity: TEST_INDEX is
  `test_df.index` from `data_pipeline.chronological_split` of that frame (the Stage 1 test split, 3,829 rows).
  Preflight finding (row order only, no outcome): data_pipeline's `sort_values('date')` is not a stable sort; 7,748 H
  positions hold a different row than a stable sort would put there, all within equal timestamps, and the two matches
  at 2025-02-01 13:00 sit on opposite sides of the 15,316-row boundary in the two orders. The flag follows
  data_pipeline's actual split, the definition every earlier stage used. TEST rows act as history: they run through
  the filters and are never scored or reported. No H row is scored.
- **home_adv** = 0.20356233139056304 for M0, M1 and M2. Asserted at every run: equal within 1e-12 to
  `stage2_dynamic.compute_home_adv` on the first 15,316 rows of cleaned, stably sorted H (and to the value from
  data_pipeline's own split). Preflight: both differences 0.0.
- **L (live).** Completed 2026-2027 matches of the 8 `data_pipeline.LEAGUES`, fetched fresh with penaltyblog
  `FootballData(league, '2026-2027').get_fixtures()`, up to 3 attempts per league; a league that cannot be fetched
  stops the run. The snapshot keeps every fetched row; L is the snapshot rows cleaned the same way (drop rows missing
  goals_home, goals_away or datetime, `date = pd.to_datetime(datetime)`, stable sort on date, reset index). Every
  fetched row must be season 2026-2027 and every L row dated after the last H date (asserted).
- **Concatenation.** H (column frame = H, TEST flag set) then L (frame = L, TEST flag false), `ignore_index=True`,
  then a stable sort on date. If `pd.concat` raises the pandas string-dtype storage mismatch, L's string columns are
  cast to the H column dtypes; the cache and H are never altered. Whether the cast was needed is reported.
- **Scored frame.** Only L rows. Asserted: season 2026-2027, frame L, TEST flag false, dated after the last H date,
  and no (league, season, home, away, datetime) key equal to an H row.

## Models (all frozen; none has seen any 2026-27 result when its parameters were set)
- **M0 baseline:** `exp_model.run_filter` with `exp_model.DEFAULT_PARAMS` (reproduces Stage 2).
- **M1 P1:** `results/experiments/candidate_p1.json`, params process_noise 0.005, initial_var 0.3, cold_defence 0.3,
  clip_rates on, rho -0.04, calibration null (checked by `run_p2.load_p1`), through `exp_model.run_filter`.
- **M2 P2 goals-only:** `results/p2/candidate_p2.json` (committed-file guard and self-hash
  bf7d5226316fe2cb4473e7120c624802f7dcdbd651b603200747f179728b0e3f, checked by `run_p2.load_frozen`), `goals_only.params`
  = P1 + S0 + S1: process_noise 0.0025, initial_var 0.15, cold_defence 0.45, clip_rates on, rho -0.04, shots_w 0.5,
  through `p2_model.run_filter` (SoT columns hst, ast).
- **Reference models, descriptive only, no verdict.**
  - **M3** Stage 1 static Dixon-Coles: `stage1_baseline.fit_baseline` on a copy of all H rows (xi 0.0065, reference
    date = last H date), fitted once and never updated during L. Probabilities from `predict(home, away)` with
    penaltyblog's defaults (max_goals 15, normalize on); divided by their sum only if it differs from 1 by more than
    1e-10 (count reported). Scored on test-set rows where both teams appear in H.
  - **M4** closing-market average: columns `avg_ch`, `avg_cd`, `avg_ca`, valid when all three are numeric and > 1,
    overround removed proportionally (m_k = (1/o_k) / sum_j (1/o_j); `exp_harness.market_probs`). Test-set rows
    without a valid triple are left out of M4 tables (count reported). Closing odds are later information than any
    pre-match forecast: benchmark only.

Frozen JSON files (sha256 of the committed blob at 4233f37, and of the CRLF working copy):

| File | sha256 (git blob, LF) | sha256 (working copy, CRLF) |
|---|---|---|
| results/experiments/candidate_p1.json | a04d1755a53aa525ace6e01ffea98f915d09fb01ae3945504e23d9c97993af55 | 74d14ea83d9e390b1d025dc2fa2b27a329cca2c668376915616d8296ee6cb635 |
| results/p2/candidate_p2.json | 772b9137ee1db11b4d6ba7ab56355b49c05d18fcb1b442965136343a99656533 | a670a300bf1f25141767ee6f76d2d159d19d18500044ba425f8704609cb6f1b5 |
| results/experiments/incumbent.json | ae7ae966625bd4f06348b05ac668298a30e00ebf5babea89a67e83c0977a52ec | 92c49215c38045f16104fb02ce4e2e06c1c20b858b83e7fd5ce28b0c1173d8bd |
| results/p2/incumbent.json | f6ac2317d2082a12ed7d61995fd689a374934dede8b4f48c82d4fc6d0d1013c9 | 76218c21bd80f25921ef7fe2c7fb663172b4cb1ef0386e4f5a16c80c61bb111c |

The two incumbent files pin the same parameters as the two candidates; they are hashed because M0 has no file. Every
scoring run checks that the committed blobs of these four files still have these hashes.

## Forecast protocol
Each filter runs once over the concatenation of H and L. A row's forecast uses only earlier rows; the filter then
updates with that row's result (M2 also with its shots on target, scaled by goals per shot on target over strictly
earlier matches). This is identical to every earlier stage and to live use. Teams in L absent from H are newcomers and
start cold exactly as in every earlier stage (P1 and P2: cold_defence for teams first seen after their league's first
season). Before any score, every scoring run checks, forecasts only:
- `p2_model.run_filter` with shots_w 0 and the P1 parameters equals `exp_model.run_filter` P1 on all concatenated rows
  (three probabilities and two rates), max absolute difference at most 1e-12, else STOP;
- M0 equals `stage2_dynamic.run_sequential_filter` on all concatenated rows (three probabilities), at most 1e-12, else
  STOP.

## Test set
L rows in the snapshot, excluding:
1. fixtures in `forward/predictions.jsonl` (the working file, read only; it must pass `forward_logger.verify_log`, else
   STOP), matched on (league, season, home, away), so this stream and the forward log are disjoint. The number
   excluded is reported;
2. rows involving a flagged newcomer (below), listed.

Newcomers are teams in L that appear in no H row (home or away, any league). They are kept. Name audit: for each
newcomer, the best rapidfuzz `fuzz.WRatio` against the H team names of the same league (teams in H rows of that
league), computed on the raw names and again with `processor=rapidfuzz.utils.default_process`; the team is flagged if
either best score is 88 or more (stricter reading: flag if either). Flagged teams are listed and their rows excluded
from the test set; names are never merged. If any league has more than 4 newcomers: STOP (a systematic naming change).

Data checks (no outcome): a duplicate (league, datetime, home, away) row, a duplicate (league, season, home, away)
pair, or a team with two L matches on one calendar day: STOP (no de-duplication rule is pre-registered, and rows are
not changed after the data is seen). Fewer than 200 completed L rows, or a league with none: STOP.

## Primary hypotheses (pre-registered, two tests)
- **T1:** M1 minus M0, mean per-match log-loss on the test set.
- **T2:** M2 minus M1, same metric.

Per-match log-loss = -log(max(p of the observed outcome, 1e-15)) (`exp_harness.row_scores`, the scale of
`metrics.probability_metrics`); the outcome (home win, draw, away win) comes from full-time goals
(`metrics.outcome_classes`). M0, M1 and M2 forecast every test-set row.

CI: paired bootstrap resampling matches with replacement, 2000 resamples, `numpy.random.default_rng(20261031)`
drawing one index matrix of shape (2000, n), used for both tests; the interval is the 1.25% and 98.75% quantiles
(numpy default linear interpolation) of the resampled mean differences, a 97.5% two-sided interval (Bonferroni,
1 - 0.05/2, for two tests). **Rule:** an improvement is accepted only if the upper bound is below 0. Otherwise the
report says "no detectable improvement" with the point estimate and CI. The verdict comes from the first snapshot
only. Each test also reports n, each model's mean log-loss, the standard error (sample standard deviation of the
per-match differences, ddof 1, over the square root of n) and the CI half-width ((upper - lower) / 2).

## Secondary, descriptive, no verdict
- Week-block bootstrap CI for both differences: `exp_harness.week_block_ci(delta, dates, level=0.975,
  n_resamples=2000, seed=20261031)` (calendar weeks, pandas period 'W').
- RPS, Brier, log-loss and accuracy (`metrics.probability_metrics`) of M0, M1 and M2 on the test set; per league;
  newcomer matches (at least one team absent from H) versus established matches (both teams in H), with counts.
- Mean predicted draw probability versus observed draw rate per model: M0-M2 on the test set, M3 on its rows, M4 on
  its rows.
- M3 against M0-M2 on M3's rows; the gap of M0-M2 to M4 (model minus market) on test rows with closing odds.
- No post-hoc power claim.

## Snapshot and manifest
- `results/live2627/snapshot_<YYYYMMDD>.json` (UTC fetch date): `{"snapshot_date", "rows"}`, rows in fetch order
  (league order of `data_pipeline.LEAGUES`, source order within a league), every fetched row, fields: league, season,
  datetime (`YYYY-MM-DDTHH:MM:SS` or null), home, away, goals_home, goals_away (integer or null), hst, ast (number or
  null; null when the column is absent), avg_ch, avg_cd, avg_ca (number or null; non-numeric source text is written as
  null and counted).
- Canonical row JSON: `json.dumps(rows, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)`;
  its UTF-8 sha256 is the snapshot hash.
- `results/live2627/manifest_<YYYYMMDD>.json`: fetched_at_utc, source, per-league counts (fetched, completed), earliest
  and latest date, columns present (fetched columns and snapshot fields), rows_sha256, the pre-registration commit,
  the forward-log state read (rows, last row_hash), non-numeric odds count.
- `results/live2627/data_audit.md` (first snapshot): counts per league, newcomer list and name audit, shots and
  closing-odds missing shares, duplicate rows, overlap with the forward log. Counts and missing shares only; no
  outcome metric. JSON and Markdown only; no csv or pkl is tracked. A snapshot is never overwritten.

## Scoring guard
The scoring function raises unless `live2627/PREREGISTRATION.md` is tracked, has no uncommitted change and is
unchanged since the commit that added it; the snapshot file and its manifest are tracked with no uncommitted change;
and the snapshot's canonical sha256 equals the manifest's rows_sha256.

## Runs (`live2627.py`)
- `--snapshot`: the first fetch (Phase 2): snapshot, manifest and data audit; no score. Refuses if a snapshot exists.
- default: the primary scoring of snapshot 1 (the earliest snapshot), once; refuses if `results/live2627/primary.json`
  exists. Writes `primary.md` and `primary.json`, labelled "LIVE 2026-27, retrospective forecasts (not timestamped
  before kickoff)".
- `--refresh`: if the latest snapshot is later than snapshot 1 and has no cumulative report, it scores it (the guard
  applies, so it must be committed first) and writes `cumulative_<YYYYMMDD>.md` and `.json`, labelled "cumulative
  update; the verdict stays with snapshot 1". Otherwise it fetches a new dated snapshot and manifest (refusing if one
  exists for that date) and asks for them to be committed before the next `--refresh` scores them. Same frozen models,
  rules, test-set definition and stop conditions; its tests and CIs are descriptive.
- `--verify`: the pre-registration is committed and unchanged; every snapshot's canonical sha256 matches its manifest;
  every scored row listed in `primary.json` and `cumulative_*.json` is an L row of its snapshot (season 2026-2027,
  dated after the last H date, no H key), so no TEST row was scored.

## Errors and stop conditions
If the scoring run errors, only the code bug is fixed, the run is repeated once, and both are logged in DECISIONS.md.
No parameter, row or rule changes. STOP if: an anchor moves; an equality check exceeds 1e-12; a league has more than 4
newcomers; fewer than 200 completed rows or a league with none; a duplicate row or pair, or a team twice on one day; a
leak cannot be resolved; the forward log fails verification; a step needs a file outside the session exceptions.
