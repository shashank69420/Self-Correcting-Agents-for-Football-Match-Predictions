# Forward test pre-registration (B12, season 2026-2027)

Written and committed 2026-10-26, before any forecast was logged. Nothing below changes after the first row of
`forward/predictions.jsonl` exists; a deviation is logged in DECISIONS.md and never rewrites this file's rules.

## Purpose
Test, on matches not yet played when they are forecast, whether frozen candidate P1 forecasts outcomes better than
the Stage 2 baseline. All earlier B12 results are retrospective (the test window was examined before P1 was scored);
this is the only prospective evidence.

## Models (frozen)
- **baseline**: `exp_model.run_filter` with `exp_model.DEFAULT_PARAMS` (reproduces Stage 2).
- **P1**: `exp_model.make_params(**params)` with `params` from `results/experiments/candidate_p1.json`
  (process_noise 0.005, initial_var 0.3, cold_defence 0.3, clip_rates on, rho -0.04).
  params_sha256 = `74d14ea83d9e390b1d025dc2fa2b27a329cca2c668376915616d8296ee6cb635` (sha256 of the file's bytes).
- **home_adv** = 0.20356233139056304, fixed. At every run the logger asserts it equals, within 1e-12, the value
  `stage2_dynamic.compute_home_adv` gives on the first 15,316 rows of the cleaned, stably sorted cached frame.
- Both models are imported from `exp_model`; the logger copies none of its maths. `run_filter` keeps team states
  internal, so the logger observes the state objects that `run_filter` passes to its own `update_step`, then
  forecasts each fixture by cloning the two team states, applying one `predict_step` each, and calling
  `dixon_coles_probs` with the model's clip and rho. A test checks this against `run_filter`'s own pre-match
  forecast on real historical rows (tolerance 1e-12).
- Each row records `code_commit`, `code_dirty` and `params_sha256`.

## History and forecast
- History = the cache `data/fixtures_raw.pkl` (completed seasons 2019-2020 to 2025-2026) plus a fresh penaltyblog
  FootballData scrape of 2026-2027 for the 8 leagues of `data_pipeline.LEAGUES`, cleaned as `data_pipeline` does
  (drop rows missing goals or datetime, `date` from `datetime`, stable sort by date).
- The filter runs over played matches only. Fixtures never enter the filter and do not affect each other.
- A fixture team found nowhere in the history (cache plus fresh 2026-2027 results) is refused and listed: most likely
  a name mismatch. Teams seen only in 2026-2027 results are newcomers and are forecast normally.

## Source and time zone (Step 1, 2026-10-26)
- Fixtures: `https://www.football-data.co.uk/fixtures.csv`, fetched fresh at every run with a browser User-Agent.
  At discovery it had upcoming fixtures for all 8 target divisions (E0, SP1, D1, I1, F1, N1, P1, T1, plus other
  divisions that are ignored), HTTP Last-Modified Fri, 23 Oct 2026 13:46:58 GMT, kickoffs 23 to 26 October.
  Penaltyblog's 2026-2027 season files (source A) had no unplayed rows, so they are used for history and results only.
- football-data.co.uk/notes.txt (read 2026-10-26): time zone **not stated**; fixtures-file update frequency
  **not stated**. Its only timing statement concerns odds: "Betting odds for weekend games are collected Friday
  afternoons, and on Tuesday afternoons for midweek games."
- Time-zone rule (locked design): Date and Time are UK local time, converted Europe/London to UTC with `zoneinfo`.
  Supporting evidence, not a source statement: Bundesliga's standard 15:30 CET Saturday slot appears as 14:30 (6 of
  9 D1 fixtures, and 1,300 cached Bundesliga rows), Serie A's 12:30 CET slot as 11:30.
- Rows with no time, or a local time that is ambiguous or nonexistent at a clock change, are refused.

## Logging rule
- A fixture is logged only if kickoff_utc minus now_utc is more than 3 hours (exactly 3 hours is refused, so that
  `--verify`'s strict check kickoff_utc > logged_at_utc + 3h holds). now comes from `datetime.now(UTC)`; there is no
  CLI option or environment variable to set it.
- Every fixture is validated first, then all accepted rows are written in one append with flush and fsync.
- Append-only JSON lines with a hash chain: row_hash = sha256(prev_hash + canonical JSON of the row without
  row_hash), canonical = sorted keys, no spaces; the first prev_hash is 64 zeros.
- Dedupe key (league, season, home, away): a fixture already logged is skipped, so a rescheduled match keeps its
  first forecast.
- `predictions.jsonl` is never edited by hand. `--verify` recomputes the chain, checks fixture_id uniqueness, the
  3-hour rule on every row and that code_commit exists in git, and checks that the committed log is a byte prefix
  of the working file.
- Raw source odds are stored in `odds_snapshot` for reference only; no model reads them.

## Scoring
- `--score` fetches fresh 2026-2027 results and matches logged rows by (league, season, home, away), accepting a
  result only if its date is on or after the kickoff date minus 1 day. Rows are scored, pending, or unresolved
  (more than 10 days after kickoff with no accepted result). `--score` never modifies `predictions.jsonl`.
- **Primary metric:** mean per-match log-loss difference, P1 minus baseline, over scored rows (negative favours P1).
  Per-match log-loss is -log of the probability given to the observed outcome, clipped at 1e-15 as in `metrics.py`.
- **Secondary metrics:** RPS, Brier, log-loss and accuracy for each model (`metrics.probability_metrics`).
- **Claim rule:** below 600 scored matches the report is descriptive only; no inference. From 600 scored matches,
  add a 95% week-block bootstrap CI of the primary metric: 2000 resamples, seed 20261027, weeks = calendar weeks of
  the kickoff date in UTC, the same algorithm as `metrics.paired_week_block_ci` (which fixes its seed to 20260922,
  so the logger uses an equivalent function with a seed argument; a test checks it reproduces the metrics helper
  at that seed). P1 improvement is claimed only if the CI upper bound is below 0.
- **Analysis time:** the claim is evaluated once, at the first `--score` run with at least 600 scored matches; that
  report is committed as the confirmatory result. Later reports may show updated intervals, labelled follow-up
  looks, and never overwrite the verdict.

## Model freeze
No change to either model, to `home_adv`, or to `candidate_p1.json` after the first logged row. A changed model is
a new model id, logged separately (new fields or a new log), and never replaces the P1 or baseline columns.

## Limitations
- The time zone is a locked assumption supported by kickoff-slot evidence; the source does not state it.
- The fixtures file covers only a few days ahead and its update schedule is not stated; matches are logged only when
  the logger is run (by hand) while they are in the file and more than 3 hours away. Coverage is therefore partial
  and depends on run times, not on match content.
- The 2026-2027 results file may lag the fixtures: matches played but not yet in it are missing from the history,
  so a forecast can be based on a team state one or more matches old. `history_through` records the latest played
  match used.
- Forecasts use goals only: no lineups, injuries or odds. home_adv comes from the 2019-2025 training window.
- One source for fixtures, history and results (football-data.co.uk); a team-name change there would be refused, not
  guessed.
- At 600 scored matches the interval is wide relative to small effects; a null result is not evidence of equality.
