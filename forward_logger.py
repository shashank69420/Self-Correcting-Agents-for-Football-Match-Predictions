"""Pre-registered forward test of the frozen baseline and P1 forecasts (forward/PREREGISTRATION.md).

python -X utf8 forward_logger.py           log every upcoming fixture more than 3 hours away, once
python -X utf8 forward_logger.py --score   score logged rows against fresh results; writes forward/score_report.md
python -X utf8 forward_logger.py --verify  hash chain, fixture ids, 3-hour rule and code commits; exit 1 on failure

The fixture list and the 2026-2027 results are always fetched fresh; completed seasons come from the cache.
"""
import argparse
import copy
import datetime as dt
import hashlib
import io
import json
import os
import subprocess
import sys
import warnings
from unittest import mock
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import penaltyblog as pb
import requests
from penaltyblog.scrapers.common import COMPETITION_MAPPINGS

import exp_model
import metrics
from data_pipeline import LEAGUES, RAW_FIXTURES_PATH, SEASONS
from stage2_dynamic import compute_home_adv, predict_step

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
FORWARD_DIR = os.path.join(PROJECT_DIR, 'forward')
LOG_PATH = os.path.join(FORWARD_DIR, 'predictions.jsonl')
REPORT_PATH = os.path.join(FORWARD_DIR, 'score_report.md')
LOG_REPO_PATH = 'forward/predictions.jsonl'
OWN_OUTPUTS = (LOG_REPO_PATH, 'forward/score_report.md')
PARAMS_PATH = os.path.join(PROJECT_DIR, 'results', 'experiments', 'candidate_p1.json')
FIXTURES_URL = 'https://www.football-data.co.uk/fixtures.csv'
USER_AGENT = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                            '(KHTML, like Gecko) Chrome/130.0 Safari/537.36'}

SEASON = '2026-2027'
SEASON_DATES = (dt.date(2026, 7, 1), dt.date(2027, 6, 30))
HOME_ADV = 0.20356233139056304   # Stage 2's fixed training-only value; asserted against the cache at every run
TRAIN_ROWS = 15_316
FROZEN_P1 = dict(process_noise=0.005, initial_var=0.3, cold_defence=0.3, clip_rates=True, rho=-0.04)
MIN_LEAD = dt.timedelta(hours=3)
RESULT_TOLERANCE = dt.timedelta(days=1)
UNRESOLVED_AFTER = dt.timedelta(days=10)
CI_MIN_SCORED = 600
CI_SEED = 20261027
GENESIS = '0' * 64
UK = ZoneInfo('Europe/London')
DIV_TO_LEAGUE = {COMPETITION_MAPPINGS[league]['footballdata']['slug']: league for league in LEAGUES}
SOURCE_COLUMNS = {'Div', 'Date', 'Time', 'HomeTeam', 'AwayTeam', 'Referee'}
HISTORY_COLUMNS = ['competition', 'season', 'datetime', 'team_home', 'team_away', 'goals_home', 'goals_away']
MODELS = ('p1', 'base')
ROW_FIELDS = ['fixture_id', 'league', 'season', 'home', 'away', 'kickoff_utc', 'logged_at_utc', 'source_url',
              'source_fetched_at_utc', 'history_through', 'n_history_rows',
              'p1_home', 'p1_draw', 'p1_away', 'p1_lambda', 'p1_mu',
              'base_home', 'base_draw', 'base_away', 'base_lambda', 'base_mu',
              'code_commit', 'code_dirty', 'params_sha256', 'odds_snapshot', 'prev_hash', 'row_hash']


# ---------------------------------------------------------------- time

def utc_now():
    return dt.datetime.now(dt.UTC)


def iso_utc(moment):
    moment = moment.astimezone(dt.UTC)
    return moment.strftime('%Y-%m-%dT%H:%M:%S.%fZ' if moment.microsecond else '%Y-%m-%dT%H:%M:%SZ')


def parse_utc(text):
    return dt.datetime.fromisoformat(text).astimezone(dt.UTC)


def uk_to_utc(local):
    """Naive UK local time to aware UTC; ambiguous or nonexistent clock-change times raise ValueError."""
    first, second = local.replace(tzinfo=UK, fold=0), local.replace(tzinfo=UK, fold=1)
    if first.utcoffset() != second.utcoffset():
        raise ValueError(f'ambiguous or nonexistent UK local time {local}')
    return first.astimezone(dt.UTC)


def parse_kickoff(date_text, time_text):
    """football-data Date (dd/mm/yy or dd/mm/yyyy) and Time (HH:MM), UK local, to UTC."""
    if not time_text.strip():
        raise ValueError('missing time')
    date_format = '%d/%m/%y' if len(date_text.strip()) <= 8 else '%d/%m/%Y'
    try:
        local = dt.datetime.strptime(f'{date_text.strip()} {time_text.strip()}', f'{date_format} %H:%M')
    except ValueError:
        raise ValueError('unparseable date or time') from None
    return uk_to_utc(local)


# ---------------------------------------------------------------- data

def clean(raw):
    """data_pipeline's cleaning: drop rows missing goals or datetime, date from datetime, stable sort."""
    df = raw.dropna(subset=['goals_home', 'goals_away', 'datetime']).copy()
    df['date'] = pd.to_datetime(df['datetime'])
    return df.sort_values('date', kind='stable').reset_index(drop=True)


def load_cache():
    raw = pd.read_pickle(RAW_FIXTURES_PATH)
    if not set(raw['season']) <= set(SEASONS) or SEASON in set(raw['season']):
        raise ValueError(f'The cache must hold completed seasons only, found {sorted(set(raw["season"]))}')
    return raw


def check_home_adv(cache_raw):
    frame = clean(cache_raw)
    value = compute_home_adv(frame.iloc[:TRAIN_ROWS], frame.iloc[TRAIN_ROWS:])
    if abs(value - HOME_ADV) > 1e-12:
        raise AssertionError(f'home_adv {value!r} recomputed from the cache differs from {HOME_ADV!r}')
    return value


def fetch_season():
    """Fresh 2026-2027 penaltyblog scrape for the 8 leagues; any failure stops the run."""
    frames = []
    for league in LEAGUES:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', pd.errors.PerformanceWarning)
            frames.append(pb.scrapers.FootballData(league, SEASON).get_fixtures())
    return pd.concat(frames, ignore_index=True)


def build_history(cache_raw, season_raw):
    if set(season_raw['season']) != {SEASON}:
        raise ValueError(f'Fresh results must be season {SEASON} only, found {sorted(set(season_raw["season"]))}')
    raw = pd.concat([cache_raw[HISTORY_COLUMNS], season_raw[HISTORY_COLUMNS]], ignore_index=True)
    return clean(raw)


def fetch_fixtures():
    fetched_at = utc_now()
    response = requests.get(FIXTURES_URL, headers=USER_AGENT, timeout=60)
    response.raise_for_status()
    # Strings throughout: odds_snapshot keeps the source text exactly.
    fixtures = pd.read_csv(io.BytesIO(response.content), dtype=str, keep_default_na=False, encoding='utf-8-sig')
    return fixtures, FIXTURES_URL, fetched_at


def load_p1():
    with open(PARAMS_PATH, 'rb') as handle:
        content = handle.read()
    params = json.loads(content)['params']
    if params != FROZEN_P1:
        raise AssertionError(f'candidate_p1.json params {params} differ from the frozen P1 {FROZEN_P1}')
    return params, hashlib.sha256(content).hexdigest()


def frozen_models():
    params, params_sha256 = load_p1()
    return dict(p1=exp_model.make_params(**params), base=exp_model.make_params()), params_sha256


# ---------------------------------------------------------------- model

def snapshot_states(history, params, home_adv):
    """Team states after exp_model.run_filter has processed every row of history, plus its forecasts.

    run_filter keeps its states local. They are the objects it passes to its own update_step, which changes them in
    place, so recording those objects gives the final states without copying any filter maths.
    """
    original, seen = exp_model.update_step, []

    def recording_update(home_state, away_state, *args):
        seen.append((home_state, away_state))
        return original(home_state, away_state, *args)

    with mock.patch.object(exp_model, 'update_step', recording_update):
        forecasts = exp_model.run_filter(history, params, home_adv)
    if len(seen) != len(forecasts):
        raise RuntimeError('run_filter did not update once per history row')
    states = {}
    for (home_state, away_state), home, away in zip(seen, forecasts['team_home'], forecasts['team_away']):
        for team, state in ((home, home_state), (away, away_state)):
            if states.setdefault(team, state) is not state:
                raise RuntimeError(f'run_filter used more than one state object for {team}')
    return states, forecasts


def forecast_fixture(states, home, away, params, home_adv):
    """One fixture from cloned post-history states: one predict_step per team, then run_filter's forecast steps."""
    if params['drift_per_day'] or params['season_var'] or params['league_k'] is not None:
        raise ValueError('forecast_fixture supports models without drift, season variance or league effects')
    home_state = predict_step(copy.deepcopy(states[home]), params['process_noise'])
    away_state = predict_step(copy.deepcopy(states[away]), params['process_noise'])
    lambda_home = np.exp(home_state.attack_mean + away_state.defence_mean + home_adv)
    mu_away = np.exp(away_state.attack_mean + home_state.defence_mean)
    if params['clip_rates']:
        low, high = params['rate_bounds']
        lambda_home = min(max(lambda_home, low), high)
        mu_away = min(max(mu_away, low), high)
    pred_h, pred_d, pred_a = exp_model.dixon_coles_probs(lambda_home, mu_away, params['rho'])
    return {'home': pred_h, 'draw': pred_d, 'away': pred_a, 'lambda': float(lambda_home), 'mu': float(mu_away)}


# ---------------------------------------------------------------- log

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def row_hash(prev_hash, row):
    body = {key: value for key, value in row.items() if key != 'row_hash'}
    return hashlib.sha256((prev_hash + canonical(body)).encode('utf-8')).hexdigest()


def read_log(path):
    if not os.path.exists(path):
        return []
    with open(path, 'rb') as handle:
        lines = handle.read().decode('utf-8').splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def append_rows(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'ab') as handle:
        for row in rows:
            handle.write(canonical(row).encode('utf-8') + b'\n')
        handle.flush()
        os.fsync(handle.fileno())


def dedupe_key(row):
    return row['league'], row['season'], row['home'], row['away']


def git(*args):
    return subprocess.run(['git', *args], cwd=PROJECT_DIR, capture_output=True, text=True)


def commit_exists(commit):
    return bool(commit) and git('cat-file', '-e', f'{commit}^{{commit}}').returncode == 0


def code_provenance():
    head = git('rev-parse', 'HEAD')
    if head.returncode != 0:
        raise RuntimeError(f'git rev-parse HEAD failed: {head.stderr.strip()}')
    status = git('status', '--porcelain').stdout.splitlines()
    dirty = [line for line in status if line[3:].strip('"') not in OWN_OUTPUTS]
    return dict(code_commit=head.stdout.strip(), code_dirty=bool(dirty))


def verify_log(path, check_git=True):
    """Failure messages for the log at path (empty list when it passes)."""
    try:
        rows = read_log(path)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return [f'unreadable log: {error}']
    failures, prev_hash, ids, keys = [], GENESIS, set(), set()
    for number, row in enumerate(rows, start=1):
        if sorted(row) != sorted(ROW_FIELDS):
            failures.append(f'row {number}: fields {sorted(set(row) ^ set(ROW_FIELDS))} missing or unexpected')
            continue
        if row['prev_hash'] != prev_hash:
            failures.append(f'row {number}: prev_hash does not link to the previous row')
        if row['row_hash'] != row_hash(row['prev_hash'], row):
            failures.append(f'row {number}: row_hash does not match the row contents')
        prev_hash = row['row_hash']
        expected_id = f"{row['league']}|{row['kickoff_utc']}|{row['home']}|{row['away']}"
        if row['fixture_id'] != expected_id:
            failures.append(f'row {number}: fixture_id is not league|kickoff_utc|home|away')
        if row['fixture_id'] in ids:
            failures.append(f'row {number}: duplicate fixture_id {row["fixture_id"]}')
        if dedupe_key(row) in keys:
            failures.append(f'row {number}: duplicate (league, season, home, away) {dedupe_key(row)}')
        ids.add(row['fixture_id'])
        keys.add(dedupe_key(row))
        try:
            if not parse_utc(row['kickoff_utc']) > parse_utc(row['logged_at_utc']) + MIN_LEAD:
                failures.append(f'row {number}: kickoff_utc is not more than 3 hours after logged_at_utc')
        except (TypeError, ValueError) as error:
            failures.append(f'row {number}: bad timestamp: {error}')
        if check_git and not commit_exists(row['code_commit']):
            failures.append(f'row {number}: code_commit {row["code_commit"]!r} not found in git')
    if check_git and os.path.abspath(path) == os.path.abspath(LOG_PATH):
        failures += committed_prefix_failures(path)
    return failures


def committed_prefix_failures(path):
    """The committed log must be a prefix of the working file (line endings normalised)."""
    committed = subprocess.run(['git', 'show', f'HEAD:{LOG_REPO_PATH}'], cwd=PROJECT_DIR, capture_output=True)
    if committed.returncode != 0:
        return []
    with open(path, 'rb') as handle:
        working = handle.read().replace(b'\r\n', b'\n')
    if not working.startswith(committed.stdout.replace(b'\r\n', b'\n')):
        return ['working log is not an extension of the committed log (rows removed or changed)']
    return []


def plan_fixtures(fixtures, known_teams, logged_keys, now):
    """Validates every fixture. Returns accepted fixtures, refusals as (reason, description), ignored-row count."""
    accepted, refused, planned_keys, ignored = [], [], set(), 0
    for record in fixtures.to_dict('records'):
        league = DIV_TO_LEAGUE.get(record.get('Div', ''))
        if league is None:
            ignored += 1
            continue
        home, away = record['HomeTeam'].strip(), record['AwayTeam'].strip()
        description = f"{record['Div']} {record['Date']} {record['Time']} {home} v {away}"
        try:
            kickoff = parse_kickoff(record['Date'], record['Time'])
        except ValueError as error:
            refused.append((str(error) if str(error) in ('missing time', 'unparseable date or time')
                            else 'ambiguous or nonexistent UK time', description))
            continue
        key = (league, SEASON, home, away)
        unknown = [team for team in (home, away) if team not in known_teams]
        if not SEASON_DATES[0] <= kickoff.date() <= SEASON_DATES[1]:
            reason = f'outside season {SEASON}'
        elif key in logged_keys:
            reason = 'already logged'
        elif key in planned_keys:
            reason = 'duplicate in source'
        elif kickoff <= now:
            reason = 'kickoff passed'
        elif kickoff - now <= MIN_LEAD:
            reason = 'under 3 hours'
        elif unknown:
            reason = 'unknown team: ' + ', '.join(unknown)
        else:
            reason = None
        if reason is not None:
            refused.append((reason, description))
            continue
        planned_keys.add(key)
        odds = {column: value.strip() for column, value in record.items()
                if column not in SOURCE_COLUMNS and value.strip()}
        accepted.append(dict(league=league, home=home, away=away, kickoff=kickoff, odds=odds))
    return accepted, refused, ignored


def build_rows(accepted, states, models, home_adv, context, prev_hash, now):
    rows = []
    for fixture in accepted:
        kickoff_utc = iso_utc(fixture['kickoff'])
        row = dict(fixture_id=f"{fixture['league']}|{kickoff_utc}|{fixture['home']}|{fixture['away']}",
                   league=fixture['league'], season=SEASON, home=fixture['home'], away=fixture['away'],
                   kickoff_utc=kickoff_utc, logged_at_utc=iso_utc(now), odds_snapshot=fixture['odds'], **context)
        for name in MODELS:
            forecast = forecast_fixture(states[name], fixture['home'], fixture['away'], models[name], home_adv)
            total = forecast['home'] + forecast['draw'] + forecast['away']
            if not np.isfinite(list(forecast.values())).all() or abs(total - 1.0) > 1e-10:
                raise FloatingPointError(f'invalid {name} forecast for {fixture}')
            row.update({f'{name}_{field}': value for field, value in forecast.items()})
        row['prev_hash'] = prev_hash
        row['row_hash'] = prev_hash = row_hash(prev_hash, row)
        rows.append(row)
    return rows


def log_fixtures(fixtures, history, models, home_adv, provenance, log_path, now=None):
    """Forecasts every fixture that passes validation and appends them in one write.

    history: cleaned played matches. provenance: source_url, source_fetched_at_utc, code_commit, code_dirty,
    params_sha256. now is datetime.now(UTC) unless a test injects it.
    """
    existing = read_log(log_path)
    failures = verify_log(log_path, check_git=False)
    if failures:
        raise RuntimeError(f'existing log fails verification, nothing written: {failures[:3]}')
    states = {name: snapshot_states(history, models[name], home_adv)[0] for name in MODELS}
    known_teams = set(history['team_home']) | set(history['team_away'])
    now = utc_now() if now is None else now
    accepted, refused, ignored = plan_fixtures(fixtures, known_teams, {dedupe_key(r) for r in existing}, now)
    history_through = uk_to_utc(history['date'].max().to_pydatetime())
    context = dict(provenance, history_through=iso_utc(history_through), n_history_rows=int(len(history)))
    rows = build_rows(accepted, states, models, home_adv, context,
                      existing[-1]['row_hash'] if existing else GENESIS, now)
    append_rows(log_path, rows)
    return rows, refused, ignored


# ---------------------------------------------------------------- score

def paired_week_block_ci_seeded(delta, weeks, seed, n_resamples=2000):
    """95% week-block bootstrap CI of the mean of delta, same algorithm as metrics.paired_week_block_ci.

    weeks: one calendar-week label per match (metrics uses dates.dt.to_period('W')). Per-match deltas are grouped by
    week, whole weeks are resampled with replacement, and the 2.5% and 97.5% quantiles of the resampled mean deltas
    are returned. Unlike the metrics helper, which fixes seed 20260922, the seed is an argument.
    """
    weekly = pd.DataFrame(dict(week=np.asarray(weeks), delta=np.asarray(delta))).groupby('week').delta.agg(
        ['sum', 'count'])
    rng = np.random.default_rng(seed)
    resamples = rng.integers(len(weekly), size=(n_resamples, len(weekly)))
    bootstrap_delta = (weekly['sum'].to_numpy()[resamples].sum(axis=1)
                       / weekly['count'].to_numpy()[resamples].sum(axis=1))
    return np.quantile(bootstrap_delta, [.025, .975])


def outcome(goals_home, goals_away):
    return 0 if goals_home > goals_away else 1 if goals_home == goals_away else 2


def score_rows(rows, results, now=None):
    """Match logged rows to cleaned results. Returns (scored rows, pending rows, unresolved rows)."""
    now = utc_now() if now is None else now
    by_key = {}
    for result in results.sort_values('date', kind='stable').itertuples():
        by_key.setdefault((result.competition, result.season, result.team_home, result.team_away), []).append(result)
    scored, pending, unresolved = [], [], []
    for row in rows:
        kickoff = parse_utc(row['kickoff_utc'])
        earliest = kickoff.date() - RESULT_TOLERANCE
        match = next((r for r in by_key.get(dedupe_key(row), []) if r.date.date() >= earliest), None)
        if match is not None:
            scored.append(dict(row, goals_home=int(match.goals_home), goals_away=int(match.goals_away),
                               result_date=str(match.date.date()),
                               actual=outcome(match.goals_home, match.goals_away)))
        elif now > kickoff + UNRESOLVED_AFTER:
            unresolved.append(row)
        else:
            pending.append(row)
    return scored, pending, unresolved


def score_summary(rows, results, now=None):
    scored, pending, unresolved = score_rows(rows, results, now)
    summary = dict(logged=len(rows), scored=len(scored), pending=len(pending), unresolved=len(unresolved),
                   unresolved_ids=[row['fixture_id'] for row in unresolved], metrics={}, delta=None, ci=None)
    if not scored:
        return summary
    actual = np.array([row['actual'] for row in scored])
    probs = {name: np.array([[row[f'{name}_home'], row[f'{name}_draw'], row[f'{name}_away']] for row in scored])
             for name in MODELS}
    summary['metrics'] = {name: metrics.probability_metrics(probs[name], actual) for name in MODELS}
    losses = {name: -np.log(np.clip(probs[name][np.arange(len(actual)), actual], 1e-15, 1.0)) for name in MODELS}
    delta = losses['p1'] - losses['base']
    summary['delta'] = float(delta.mean())
    if len(scored) >= CI_MIN_SCORED:
        dates = pd.Series(pd.to_datetime([row['kickoff_utc'] for row in scored], utc=True)).dt.tz_localize(None)
        weeks = dates.dt.to_period('W').astype(str).to_numpy()
        summary['ci'] = [float(bound) for bound in paired_week_block_ci_seeded(delta, weeks, CI_SEED)]
    return summary


def report_text(summary, results_fetched_at, now):
    lines = ['# Forward test score report', '',
             f'Generated {iso_utc(now)} by `python -X utf8 forward_logger.py --score`; results fetched '
             f'{iso_utc(results_fetched_at)}. Rules: forward/PREREGISTRATION.md.', '',
             f"- Logged: {summary['logged']}", f"- Scored: {summary['scored']}",
             f"- Pending: {summary['pending']}",
             f"- Unresolved (more than 10 days after kickoff, no result): {summary['unresolved']}"]
    lines += [f'  - {fixture_id}' for fixture_id in summary['unresolved_ids']]
    lines.append('')
    if summary['scored'] < CI_MIN_SCORED:
        lines += [f"**DESCRIPTIVE ONLY: {summary['scored']} scored, below {CI_MIN_SCORED}; no inference.**", '']
    if summary['metrics']:
        lines += ['| Model | RPS | Brier | Log-loss | Accuracy |', '|---|---|---|---|---|']
        for name, label in (('base', 'baseline'), ('p1', 'P1')):
            m = summary['metrics'][name]
            lines.append(f"| {label} | {m['RPS']:.6f} | {m['Brier']:.6f} | {m['LogLoss']:.6f} | {m['Accuracy']:.6f} |")
        lines += ['', f"Primary: mean per-match log-loss difference, P1 minus baseline: {summary['delta']:+.6f}"]
    else:
        lines.append('No scored matches yet.')
    if summary['ci'] is not None:
        low, high = summary['ci']
        verdict = 'P1 improvement claimed' if high < 0 else 'no improvement claimed'
        lines += [f'95% week-block bootstrap CI (2000 resamples, seed {CI_SEED}): [{low:+.6f}, {high:+.6f}]; '
                  f'upper bound {"below" if high < 0 else "not below"} 0: {verdict}. The confirmatory look is the '
                  f'first report with at least {CI_MIN_SCORED} scored matches; later reports are follow-up looks.']
    return '\n'.join(lines) + '\n'


def score_log(log_path, report_path, results, results_fetched_at, now=None):
    """Reads the log (never writes it), regenerates the report and returns its text."""
    now = utc_now() if now is None else now
    text = report_text(score_summary(read_log(log_path), results, now), results_fetched_at, now)
    with open(report_path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)
    return text


# ---------------------------------------------------------------- entry points

def build_parser():
    parser = argparse.ArgumentParser(description='B12 pre-registered forward test.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--score', action='store_true', help='score logged rows against fresh 2026-2027 results')
    mode.add_argument('--verify', action='store_true', help='verify the log; exit 1 on any failure')
    return parser


def run_verify():
    rows, failures = read_log(LOG_PATH), verify_log(LOG_PATH)
    for failure in failures:
        print(f'FAIL {failure}')
    print(f'VERIFY: {"FAIL" if failures else "PASS"} ({len(rows)} rows)')
    return 1 if failures else 0


def run_score():
    if run_verify():
        print('Not scored: the log fails verification.')
        return 1
    fetched_at = utc_now()
    results = clean(fetch_season())
    print(score_log(LOG_PATH, REPORT_PATH, results, fetched_at))
    return 0


def run_log():
    failures = verify_log(LOG_PATH)
    if failures:
        print('Nothing logged: the existing log fails verification:', *failures, sep='\n  ')
        return 1
    models, params_sha256 = frozen_models()
    cache_raw = load_cache()
    check_home_adv(cache_raw)
    season_raw = fetch_season()
    history = build_history(cache_raw, season_raw)
    fixtures, source_url, fetched_at = fetch_fixtures()
    provenance = dict(source_url=source_url, source_fetched_at_utc=iso_utc(fetched_at),
                      params_sha256=params_sha256, **code_provenance())
    newcomers = sorted((set(season_raw['team_home']) | set(season_raw['team_away']))
                       - set(cache_raw['team_home']) - set(cache_raw['team_away']))
    rows, refused, ignored = log_fixtures(fixtures, history, models, HOME_ADV, provenance, LOG_PATH)
    print(f'History: {len(history)} played rows through '
          f'{iso_utc(uk_to_utc(history["date"].max().to_pydatetime()))}; '
          f'{len(newcomers)} newcomer team(s) seen only in {SEASON}: {", ".join(newcomers) or "none"}')
    print(f'Source: {source_url} fetched {provenance["source_fetched_at_utc"]}; '
          f'{len(fixtures)} rows, {ignored} in other divisions ignored')
    found = len(rows) + len(refused)
    print(f'Fixtures in the 8 leagues: {found}; logged {len(rows)}; refused {len(refused)}')
    for reason, count in pd.Series([r for r, _ in refused], dtype=object).value_counts().items():
        print(f'  refused, {reason}: {count}')
    for reason, description in refused:
        if reason.startswith('unknown team'):
            print(f'  {reason}: {description}')
    if rows:
        per_league = pd.Series([row['league'] for row in rows]).value_counts().to_dict()
        print(f'Logged per league: {per_league}')
        print(f'First kickoff logged {min(r["kickoff_utc"] for r in rows)}, last {max(r["kickoff_utc"] for r in rows)}')
    else:
        print('No fixture qualified; nothing written.')
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.verify:
        return run_verify()
    if args.score:
        return run_score()
    return run_log()


if __name__ == '__main__':
    sys.exit(main())
