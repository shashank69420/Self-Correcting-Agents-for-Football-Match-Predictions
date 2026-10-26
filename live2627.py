"""Live 2026-27: frozen models scored on completed 2026-27 league matches (live2627/PREREGISTRATION.md).

python -X utf8 live2627.py --snapshot   Phase 2: first fetch; snapshot, manifest and data audit (counts only)
python -X utf8 live2627.py              the primary scoring of snapshot 1, once
python -X utf8 live2627.py --refresh    scores a committed newer snapshot, else fetches a new dated snapshot
python -X utf8 live2627.py --verify     pre-registration unchanged, snapshot hashes, no TEST row scored

H (2019-2026, from the cache) and L (2026-2027, fetched fresh) are concatenated and each frozen filter runs once over
both; only L rows are ever scored.
"""
import argparse
import contextlib
import datetime as dt
import glob
import hashlib
import io
import json
import os
import subprocess
import sys
import unicodedata
import warnings

import numpy as np
import pandas as pd
import penaltyblog as pb
from rapidfuzz import fuzz, process, utils

import exp_harness as harness
import forward_logger
import p2_model
import run_p2
from data_pipeline import LEAGUES
from exp_model import DEFAULT_PARAMS, make_params
from exp_model import run_filter as exp_run_filter
from metrics import outcome_classes, probability_metrics
from run_experiments import FILTER_COLUMNS, load_data
from stage1_baseline import fit_baseline
from stage2_dynamic import run_sequential_filter

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS = 'results/live2627'
PREREG = 'live2627/PREREGISTRATION.md'
SEASON = '2026-2027'
HOME_ADV = 0.20356233139056304
P2_PARAMS = dict(process_noise=0.0025, initial_var=0.15, cold_defence=0.45, clip_rates=True, rho=-0.04, shots_w=0.5)
# sha256 of the committed blobs at 4233f37 (pre-registered).
FROZEN_BLOBS = {
    'results/experiments/candidate_p1.json': 'a04d1755a53aa525ace6e01ffea98f915d09fb01ae3945504e23d9c97993af55',
    'results/p2/candidate_p2.json': '772b9137ee1db11b4d6ba7ab56355b49c05d18fcb1b442965136343a99656533',
    'results/experiments/incumbent.json': 'ae7ae966625bd4f06348b05ac668298a30e00ebf5babea89a67e83c0977a52ec',
    'results/p2/incumbent.json': 'f6ac2317d2082a12ed7d61995fd689a374934dede8b4f48c82d4fc6d0d1013c9',
}
SEED = 20261031
N_RESAMPLES = 2000
LEVEL = 1 - 0.05 / 2  # 97.5%, Bonferroni for two tests
FETCH_ATTEMPTS = 3
MIN_ROWS = 200
MAX_NEWCOMERS = 4
NAME_THRESHOLD = 88
# Post-hoc stricter reading (DECISIONS.md, 2026-10-27), decided before any score: a newcomer whose Transfermarkt
# club_id appears in H under another name is an alias, flagged and excluded like a WRatio flag; names are never merged.
# Evidence: python -X utf8 live2627.py --alias-check.
CLUB_ID_ALIASES = {'Erzurumspor': dict(club_id=39722, h_name='Erzurum BB')}
TOLERANCE = 1e-12
SOT = list(p2_model.SOT_COLUMNS)
CLOSING = list(harness.MARKET_COLUMNS)  # avg_ch, avg_cd, avg_ca
SNAPSHOT_FIELDS = ['league', 'season', 'datetime', 'home', 'away', 'goals_home', 'goals_away', *SOT, *CLOSING]
FRAME_COLUMNS = FILTER_COLUMNS + SOT + CLOSING
MODELS = {'M0': 'M0 baseline', 'M1': 'M1 P1', 'M2': 'M2 P2 goals-only', 'M3': 'M3 Stage 1 static DC',
          'M4': 'M4 closing average'}
TESTS = {'T1': ('M1', 'M0'), 'T2': ('M2', 'M1')}
LABEL = 'LIVE 2026-27, retrospective forecasts (not timestamped before kickoff)'
CUMULATIVE_LABEL = 'cumulative update; the verdict stays with snapshot 1'
WORDING = ('Parameters were fixed before 2026-27 data was fetched. Forecasts were recomputed after the matches were '
           'played and are not timestamped before kickoff. Team ratings update with each result as it arrives.')
SOURCE = (f"penaltyblog {pb.__version__} FootballData(league, '{SEASON}').get_fixtures() (football-data.co.uk), "
          'the 8 data_pipeline.LEAGUES')


# ---------------------------------------------------------------- files and git

def git(*args, root=PROJECT_DIR):
    return subprocess.run(['git', *args], cwd=root, capture_output=True, text=True)


def rel(name):
    return f'{RESULTS}/{name}'


def snapshot_name(date):
    return rel(f'snapshot_{date}.json')


def manifest_name(date):
    return rel(f'manifest_{date}.json')


def read_json(relpath, root=PROJECT_DIR):
    with open(os.path.join(root, relpath), encoding='utf-8') as handle:
        return json.load(handle)


def write_text(relpath, text, root=PROJECT_DIR, overwrite=False):
    path = os.path.join(root, relpath)
    if os.path.exists(path) and not overwrite:
        raise SystemExit(f'{relpath} exists; it is never overwritten.')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)


def write_json(relpath, payload, root=PROJECT_DIR):
    write_text(relpath, json.dumps(payload, indent=2, allow_nan=False) + '\n', root)


def rows_sha256(rows):
    """sha256 of the canonical row JSON (sorted keys, no spaces, ASCII; forward_logger.canonical)."""
    return hashlib.sha256(forward_logger.canonical(rows).encode('utf-8')).hexdigest()


def snapshot_text(date, rows):
    """The snapshot file: one canonical row per line, so the file is readable and diffs stay small."""
    body = ',\n'.join(forward_logger.canonical(row) for row in rows)
    return f'{{"snapshot_date": "{date}", "rows": [\n{body}\n]}}\n'


def snapshot_dates(root=PROJECT_DIR):
    names = glob.glob(os.path.join(root, RESULTS, 'snapshot_*.json'))
    return sorted(os.path.basename(name)[len('snapshot_'):-len('.json')] for name in names)


def provenance(root=PROJECT_DIR):
    status = [line for line in git('status', '--porcelain', root=root).stdout.splitlines() if line.strip()]
    return dict(code_commit=git('rev-parse', 'HEAD', root=root).stdout.strip(), code_dirty=bool(status))


# ---------------------------------------------------------------- guards

def committed_unchanged(relpath, root=PROJECT_DIR):
    """None if relpath is tracked with no uncommitted change, else the reason."""
    if git('ls-files', '--error-unmatch', relpath, root=root).returncode != 0:
        return f'{relpath} is not committed'
    if git('diff', '--quiet', 'HEAD', '--', relpath, root=root).returncode != 0:
        return f'{relpath} differs from the committed version'
    return None


def preregistration_failures(root=PROJECT_DIR):
    """The pre-registration is committed, has no uncommitted change, and no commit after the one that added it."""
    failure = committed_unchanged(PREREG, root)
    if failure:
        return [failure]
    commits = git('log', '--format=%H', '--', PREREG, root=root).stdout.split()
    if len(commits) != 1:
        return [f'{PREREG} changed after the commit that added it ({len(commits)} commits touch it)']
    return []


def snapshot_failures(date, root=PROJECT_DIR, require_committed=True):
    """The snapshot's canonical sha256 equals its manifest's; with require_committed, both files are committed."""
    failures = []
    names = (snapshot_name(date), manifest_name(date))
    for name in names:
        if not os.path.isfile(os.path.join(root, name)):
            return [f'{name} does not exist']
        if require_committed:
            failure = committed_unchanged(name, root)
            failures += [failure] if failure else []
    try:
        snapshot, manifest = (read_json(name, root) for name in names)
    except ValueError as error:
        return failures + [f'snapshot {date} unreadable: {error}']
    if snapshot.get('snapshot_date') != date or manifest.get('snapshot_date') != date:
        failures.append(f'snapshot {date}: snapshot_date fields do not match the file names')
    if rows_sha256(snapshot.get('rows', [])) != manifest.get('rows_sha256'):
        failures.append(f'snapshot {date}: rows sha256 does not match its manifest')
    return failures


def require_scorable(date, root=PROJECT_DIR):
    """Scoring guard: raises unless the pre-registration is committed and unchanged and the snapshot matches its
    committed manifest."""
    failures = preregistration_failures(root) + snapshot_failures(date, root)
    if failures:
        raise RuntimeError('Scoring refused: ' + '; '.join(failures))


def require_frozen_blobs(root=PROJECT_DIR):
    """The committed frozen JSON files still have their pre-registered sha256 and no uncommitted change."""
    failures = []
    for name, expected in FROZEN_BLOBS.items():
        blob = subprocess.run(['git', 'show', f'HEAD:{name}'], cwd=root, capture_output=True).stdout
        if hashlib.sha256(blob).hexdigest() != expected:
            failures.append(f'{name}: committed sha256 differs from the pre-registered value')
        failure = committed_unchanged(name, root)
        failures += [failure] if failure else []
    if failures:
        raise RuntimeError('Frozen files changed: ' + '; '.join(failures))


def accepted(ci_high):
    """The pre-registered rule: an improvement only if the CI upper bound is below 0."""
    return bool(ci_high < 0)


# ---------------------------------------------------------------- data

@contextlib.contextmanager
def quiet_penaltyblog():
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', pd.errors.PerformanceWarning)
        yield


def load_history():
    """H (data_pipeline's frame, TEST rows flagged before any concatenation) after both home_adv asserts."""
    forward_logger.check_home_adv(forward_logger.load_cache())  # first 15,316 rows of the stably sorted cache
    df, _, test_index, home_adv = load_data()  # data_pipeline's own order and split
    if abs(home_adv - HOME_ADV) > TOLERANCE or forward_logger.HOME_ADV != HOME_ADV:
        raise AssertionError(f'home_adv {home_adv!r} from data_pipeline differs from {HOME_ADV!r}')
    with quiet_penaltyblog():  # the penaltyblog-built frame is fragmented
        return df.assign(frame='H', is_test=df.index.isin(test_index))


def fetch_live():
    """Fresh 2026-2027 fixtures for the 8 leagues (league-major, as data_pipeline); a league that fails 3 times stops."""
    frames, fetched_at = [], dt.datetime.now(dt.UTC)
    for league in LEAGUES:
        for attempt in range(1, FETCH_ATTEMPTS + 1):
            try:
                with quiet_penaltyblog():
                    frames.append(pb.scrapers.FootballData(league, SEASON).get_fixtures())
                print(f'  fetched {league} {SEASON}: {len(frames[-1])} rows')
                break
            except Exception as error:  # noqa: BLE001 - recorded, retried, then a STOP
                if attempt == FETCH_ATTEMPTS:
                    raise SystemExit(f'STOP: {league} {SEASON} could not be fetched: {error!r}')
    return pd.concat(frames, ignore_index=True), fetched_at


def snapshot_rows(raw):
    """Every fetched row in the snapshot fields. Non-numeric goals, SoT or odds text becomes null and is counted."""
    numbers, non_numeric = {}, {}
    for column in ['goals_home', 'goals_away', *SOT, *CLOSING]:
        if column not in raw.columns:
            numbers[column], non_numeric[column] = pd.Series(np.nan, index=raw.index), 0
            continue
        numbers[column] = pd.to_numeric(raw[column], errors='coerce')
        non_numeric[column] = int((numbers[column].isna() & raw[column].notna()).sum())
    stamps = pd.to_datetime(raw['datetime']) if 'datetime' in raw.columns else pd.Series(pd.NaT, index=raw.index)
    rows = []
    for position in range(len(raw)):
        stamp = stamps.iloc[position]
        row = dict(league=str(raw['competition'].iloc[position]), season=str(raw['season'].iloc[position]),
                   datetime=None if pd.isna(stamp) else stamp.strftime('%Y-%m-%dT%H:%M:%S'),
                   home=str(raw['team_home'].iloc[position]), away=str(raw['team_away'].iloc[position]))
        for column, values in numbers.items():
            value = values.iloc[position]
            if pd.isna(value):
                row[column] = None
            elif column.startswith('goals'):
                if value != int(value):
                    raise ValueError(f'Non-integer goals in row {position}: {value}')
                row[column] = int(value)
            else:
                row[column] = float(value)
        rows.append(row)
    return rows, non_numeric


def raw_frame(rows):
    """Snapshot rows as a frame with the pipeline's column names."""
    frame = pd.DataFrame(rows, columns=SNAPSHOT_FIELDS).rename(
        columns={'league': 'competition', 'home': 'team_home', 'away': 'team_away'})
    frame['datetime'] = pd.to_datetime(frame['datetime'])
    for column in ['goals_home', 'goals_away', *SOT, *CLOSING]:
        frame[column] = pd.to_numeric(frame[column]).astype(float)
    if set(frame['season']) != {SEASON} or not set(frame['competition']) <= set(LEAGUES):
        raise ValueError(f'Snapshot rows must be {SEASON} in the 8 leagues: {sorted(set(frame["season"]))}')
    return frame


def live_frame(rows):
    """L: the snapshot's rows cleaned like data_pipeline (forward_logger.clean: dropna, date, stable sort)."""
    live = forward_logger.clean(raw_frame(rows))
    return live.astype({'goals_home': 'int64', 'goals_away': 'int64'})


def team_days(frame):
    teams = pd.concat([frame[['date', 'team_home']].rename(columns={'team_home': 'team'}),
                       frame[['date', 'team_away']].rename(columns={'team_away': 'team'})])
    return int(teams.assign(day=teams['date'].dt.normalize()).duplicated(['day', 'team']).sum())


def name_audit(history, live, aliases=CLUB_ID_ALIASES):
    """Newcomers (L teams in no H row) with their best WRatio against H names of the same league, raw and processed.
    flagged: WRatio flag (88 or more) or a club_id alias in aliases."""
    h_teams = set(history['team_home']) | set(history['team_away'])
    records = []
    for league in LEAGUES:
        rows = live.loc[live['competition'] == league]
        h_rows = history.loc[history['competition'] == league]
        h_names = sorted(set(h_rows['team_home']) | set(h_rows['team_away']))
        for team in sorted((set(rows['team_home']) | set(rows['team_away'])) - h_teams):
            raw_match, raw_score, _ = process.extractOne(team, h_names, scorer=fuzz.WRatio)
            proc_match, proc_score, _ = process.extractOne(team, h_names, scorer=fuzz.WRatio,
                                                           processor=utils.default_process)
            wratio = bool(max(raw_score, proc_score) >= NAME_THRESHOLD)
            alias = aliases.get(team)
            records.append(dict(league=league, team=team, best_raw=raw_match, wratio_raw=float(raw_score),
                                best_processed=proc_match, wratio_processed=float(proc_score), flagged_wratio=wratio,
                                alias_of=f'{alias["h_name"]} (club_id {alias["club_id"]})' if alias else '',
                                flagged=wratio or alias is not None))
    return pd.DataFrame(records, columns=['league', 'team', 'best_raw', 'wratio_raw', 'best_processed',
                                          'wratio_processed', 'flagged_wratio', 'alias_of', 'flagged'])


def ascii_name(name):
    """default_process, hyphens as spaces, accents removed: for the club-name lookup in the alias check."""
    folded = unicodedata.normalize('NFKD', utils.default_process(str(name).replace('-', ' ')))
    return ' '.join(folded.encode('ascii', 'ignore').decode().split())


def alias_check(history, live):
    """Club_id alias check (post-hoc stricter reading): for each newcomer, the top 3 H names across all leagues by
    WRatio (raw and processed) with their club_ids; the newcomer's own club_id(s) are the Transfermarkt clubs whose
    name or code (clubs.csv.gz) or game name (games.csv.gz) contains its folded name. H names get their club_id from the
    fixture link of the lineup audit (lineup.link_fixtures, unchanged). An alias is a newcomer club_id that appears in
    H under another name. Returns (records, H name -> club_id)."""
    from lineup import link_fixtures, load_local_tables
    tables = load_local_tables()
    with contextlib.redirect_stdout(io.StringIO()):
        links = link_fixtures(history.drop(columns=['frame', 'is_test']), tables)
    h_ids = {}
    for side in ('home', 'away'):
        for team, club_id in zip(history[f'team_{side}'], links[f'{side}_club_id']):
            if pd.notna(club_id):
                h_ids.setdefault(team, set()).add(int(club_id))
    if any(len(ids) != 1 for ids in h_ids.values()) or set(h_ids) != set(history['team_home']) | set(
            history['team_away']):
        raise RuntimeError('An H name has no club_id or more than one; the alias check cannot decide.')
    h_ids = {team: ids.pop() for team, ids in h_ids.items()}
    names_by_id = {}
    for team, club_id in h_ids.items():
        names_by_id.setdefault(club_id, []).append(team)
    clubs, games = tables['clubs'], tables['games']
    tm_names = pd.concat([clubs[['club_id', 'name']], clubs[['club_id', 'club_code']].set_axis(['club_id', 'name'],
                                                                                               axis=1)]
                         + [games[[f'{s}_club_id', f'{s}_club_name']].set_axis(['club_id', 'name'], axis=1)
                            for s in ('home', 'away')]).dropna().drop_duplicates()
    tm_names = tm_names.assign(club_id=tm_names['club_id'].astype('int64'), folded=tm_names['name'].map(ascii_name))
    club_name = dict(zip(clubs['club_id'].astype('int64'), clubs['name']))
    all_h = sorted(h_ids)
    records = []
    for row in name_audit(history, live, aliases={}).itertuples():
        top = {kind: [(name, round(float(score), 1), h_ids[name]) for name, score, _ in
                      process.extract(row.team, all_h, scorer=fuzz.WRatio, processor=processor, limit=3)]
               for kind, processor in (('raw', None), ('processed', utils.default_process))}
        hits = tm_names.loc[tm_names['folded'].str.contains(ascii_name(row.team), regex=False)]
        own = {int(club_id): sorted(set(hits.loc[hits['club_id'] == club_id, 'name']))
               for club_id in sorted(set(hits['club_id']))}
        nearest = [(name, round(float(score), 1), int(club_id)) for name, score, club_id in process.extract(
            row.team, club_name, scorer=fuzz.WRatio, processor=utils.default_process, limit=2)]
        in_h = {club_id: names_by_id[club_id] for club_id in own if club_id in names_by_id}
        records.append(dict(league=row.league, team=row.team, top3_raw=top['raw'], top3_processed=top['processed'],
                            top_club_ids=sorted({c for kind in top.values() for _, _, c in kind}),
                            own_club_ids=own, nearest_clubs=nearest, club_ids_in_h=in_h,
                            alias=bool(in_h), wratio_flagged=bool(row.flagged_wratio)))
    return records, h_ids


def run_alias_check():
    """Prints the alias-check evidence (read only) and whether it matches CLUB_ID_ALIASES; 1 if it does not."""
    history = load_history()
    live = live_frame(read_json(snapshot_name(snapshot_dates()[0]))['rows'])
    records, _ = alias_check(history, live)
    for r in records:
        print(f'\n{r["team"]} ({r["league"]}); WRatio rule flag: {r["wratio_flagged"]}')
        for kind in ('raw', 'processed'):
            print(f'  top 3 H names, all leagues, {kind}: ' +
                  ', '.join(f'{name} {score} (club_id {club_id})' for name, score, club_id in r[f'top3_{kind}']))
        print(f'  own club_id(s) by name in clubs/games: {r["own_club_ids"] or "none found"}')
        print('  nearest clubs.name by WRatio (context only): ' +
              ', '.join(f'{name} {score} ({club_id})' for name, score, club_id in r['nearest_clubs']))
        print(f'  own club_id(s) in H under another name: {r["club_ids_in_h"] or "none"} -> '
              f'{"ALIAS" if r["alias"] else "no alias"}')
    found = {r['team']: r['club_ids_in_h'] for r in records if r['alias']}
    expected = {team: {alias['club_id']: [alias['h_name']]} for team, alias in CLUB_ID_ALIASES.items()}
    flagged = {r['team'] for r in records if r['alias']}
    excluded = live.loc[live['team_home'].isin(flagged) | live['team_away'].isin(flagged)]
    print(f'\nWRatio rule: flagged {sum(r["wratio_flagged"] for r in records)} at WRatio >= {NAME_THRESHOLD}.')
    print(f'Alias check: {len(found)} flagged: {found}. Matches CLUB_ID_ALIASES: {found == expected}.')
    print(f'L rows involving a club_id alias: {len(excluded)}; per league: '
          f'{excluded["competition"].value_counts().to_dict()}')
    return 0 if found == expected else 1


def data_checks(history, live, aliases=CLUB_ID_ALIASES):
    """Counts and stop conditions only (no outcome is read)."""
    names = name_audit(history, live, aliases)
    per_league = {league: int((live['competition'] == league).sum()) for league in LEAGUES}
    counts = names.groupby('league').size()
    newcomers = {league: int(counts.get(league, 0)) for league in LEAGUES}
    checks = dict(completed=len(live), per_league=per_league, newcomers_per_league=newcomers,
                  duplicate_rows=int(live.duplicated(['competition', 'datetime', 'team_home', 'team_away']).sum()),
                  duplicate_pairs=int(live.duplicated(['competition', 'season', 'team_home', 'team_away']).sum()),
                  team_twice_a_day=team_days(live))
    stops = []
    if len(live) < MIN_ROWS:
        stops.append(f'{len(live)} completed rows, fewer than {MIN_ROWS}')
    stops += [f'{league} has no completed row' for league, count in per_league.items() if count == 0]
    stops += [f'{league} has {count} newcomers (more than {MAX_NEWCOMERS})'
              for league, count in newcomers.items() if count > MAX_NEWCOMERS]
    stops += [f'{checks[key]} {key.replace("_", " ")}' for key in ('duplicate_rows', 'duplicate_pairs',
                                                                    'team_twice_a_day') if checks[key]]
    return names, checks, stops


def forward_state(path=forward_logger.LOG_PATH):
    """Keys (league, season, home, away) of the forward log, after forward_logger.verify_log; read only."""
    failures = forward_logger.verify_log(path)
    if failures:
        raise SystemExit(f'STOP: the forward log fails verification: {failures[:3]}')
    rows = forward_logger.read_log(path)
    return ({forward_logger.dedupe_key(row) for row in rows},
            dict(rows=len(rows), last_row_hash=rows[-1]['row_hash'] if rows else forward_logger.GENESIS))


def concatenate(history, live):
    """H then L with the frame and TEST flags, stable sort on date; (frame, whether L's string dtypes were cast)."""
    columns = FRAME_COLUMNS + ['frame', 'is_test']
    if (live['date'] <= history['date'].max()).any():
        raise AssertionError('An L row is not dated after the last H date.')
    h, l = history[columns], live.assign(frame='L', is_test=False)[columns]
    try:
        both, cast = pd.concat([h, l], ignore_index=True), False
    except (TypeError, ValueError):  # string-dtype storage mismatch: cast L to the H dtypes, never the cache
        strings = {c: h[c].dtype for c in columns if pd.api.types.is_string_dtype(h[c]) and h[c].dtype != l[c].dtype}
        both, cast = pd.concat([h, l.astype(strings)], ignore_index=True), True
    return both.sort_values('date', kind='stable'), cast


def assert_live_only(scored, history):
    """A scored frame may contain only L rows."""
    if not (scored['frame'] == 'L').all() or scored['is_test'].any():
        raise AssertionError('An H or TEST row reached the scored frame.')
    if set(scored['season']) - {SEASON} or (scored['date'] <= history['date'].max()).any():
        raise AssertionError(f'A scored row is not a {SEASON} match after the last H date.')
    key = ['competition', 'season', 'team_home', 'team_away', 'date']
    h_keys = set(map(tuple, history[key].astype(str).to_numpy()))
    if any(tuple(row) in h_keys for row in scored[key].astype(str).to_numpy()):
        raise AssertionError('A scored row has the key of an H row.')


def select_scored(both, history, forward_keys, flagged):
    """(test-set rows, rows excluded as forward-logged, rows excluded for a flagged name)."""
    live = both.loc[both['frame'] == 'L']
    keys = zip(live['competition'], live['season'], live['team_home'], live['team_away'])
    logged = np.array([key in forward_keys for key in keys], dtype=bool)
    named = (live['team_home'].isin(flagged) | live['team_away'].isin(flagged)).to_numpy()
    scored = live.loc[~logged & ~named]
    assert_live_only(scored, history)
    return scored, live.loc[logged], live.loc[named & ~logged]


# ---------------------------------------------------------------- models

def load_models(root=PROJECT_DIR):
    """Frozen parameters: P1 (run_p2.load_p1 check) and the P2 goals-only set (committed-file guard and self-hash)."""
    require_frozen_blobs(root)
    p1 = run_p2.load_p1()
    frozen = run_p2.load_frozen(root)
    if frozen['goals_only']['params'] != P2_PARAMS or frozen['home_adv'] != HOME_ADV:
        raise RuntimeError('candidate_p2.json differs from the pre-registered P2 parameters or home_adv.')
    return p1, dict(frozen['goals_only']['params']), frozen['sha256']


def forecasts(both, p1, p2_params, home_adv=HOME_ADV):
    """M0, M1 and M2 for every row of the concatenation, each filter run once; then the two equality checks
    (forecasts only, before any score). An equality above 1e-12 stops the run."""
    goals = both[FILTER_COLUMNS]
    with_shots = both[FILTER_COLUMNS + SOT]
    result = {'M0': exp_run_filter(goals, DEFAULT_PARAMS, home_adv),
              'M1': exp_run_filter(goals, make_params(**p1), home_adv),
              'M2': p2_model.run_filter(with_shots, p2_params, home_adv)}
    w0 = p2_model.run_filter(with_shots, dict(p1, shots_w=0.0), home_adv)
    stage2, _ = run_sequential_filter(goals, home_adv)
    rates = harness.PROB_COLUMNS + ['lambda_home', 'mu_away']
    checks = {}
    for name, (ours, reference, columns) in {
            'p2_model shots_w 0 vs exp_model P1 (probabilities and rates)': (w0, result['M1'], rates),
            'M0 vs stage2_dynamic.run_sequential_filter (probabilities)': (result['M0'], stage2,
                                                                           harness.PROB_COLUMNS)}.items():
        same = ours.index.equals(reference.index)
        checks[name] = (float(np.abs(ours[columns].to_numpy(float) - reference[columns].to_numpy(float)).max())
                        if same else float('inf'))
    failed = {name: value for name, value in checks.items() if not value <= TOLERANCE}
    if failed:
        raise SystemExit(f'STOP: equality check above {TOLERANCE}: {failed}')
    return result, checks


def stage1_reference(history, rows):
    """M3: Stage 1 Dixon-Coles fitted once on all H rows; (probabilities, row mask, renormalized count) for rows
    whose two teams appear in H."""
    train = history[['date', 'team_home', 'team_away', 'goals_home', 'goals_away']].copy()
    with quiet_penaltyblog(), contextlib.redirect_stdout(io.StringIO()):
        model = fit_baseline(train)
    known = set(train['team_home']) | set(train['team_away'])
    mask = (rows['team_home'].isin(known) & rows['team_away'].isin(known)).to_numpy()
    probs, renormalized = [], 0
    for home, away in zip(rows['team_home'][mask], rows['team_away'][mask]):
        with quiet_penaltyblog():
            grid = model.predict(home, away)
        p = np.array([grid.home_win, grid.draw, grid.away_win], dtype=float)
        if abs(p.sum() - 1.0) > 1e-10:
            p, renormalized = p / p.sum(), renormalized + 1
        probs.append(p)
    return np.array(probs, dtype=float).reshape(-1, 3), mask, renormalized


# ---------------------------------------------------------------- statistics

def match_bootstrap(deltas, seed=SEED, n_resamples=N_RESAMPLES, level=LEVEL):
    """Paired bootstrap over matches: one (n_resamples, n) index matrix from default_rng(seed), shared by every
    difference; the (1 - level)/2 and (1 + level)/2 quantiles of the resampled mean differences."""
    deltas = {name: np.asarray(delta, dtype=float) for name, delta in deltas.items()}
    n = len(next(iter(deltas.values())))
    index = np.random.default_rng(seed).integers(n, size=(n_resamples, n))
    quantiles = [round((1 - level) / 2, 12), round((1 + level) / 2, 12)]
    return {name: tuple(float(v) for v in np.quantile(delta[index].mean(axis=1), quantiles))
            for name, delta in deltas.items()}


def run_tests(loss, dates):
    """T1 and T2: mean log-loss differences, 97.5% match-bootstrap CIs and the rule; week-block CIs (descriptive)."""
    deltas = {name: loss[first] - loss[second] for name, (first, second) in TESTS.items()}
    cis = match_bootstrap(deltas)
    weeks = pd.Series(np.asarray(dates))
    results = {}
    for name, (first, second) in TESTS.items():
        delta, (low, high) = deltas[name], cis[name]
        week_low, week_high, _ = harness.week_block_ci(delta, weeks, level=LEVEL, n_resamples=N_RESAMPLES, seed=SEED)
        results[name] = dict(comparison=f'{MODELS[first]} minus {MODELS[second]}', n=int(len(delta)),
                             first=float(loss[first].mean()), second=float(loss[second].mean()),
                             mean_delta=float(delta.mean()), se=float(delta.std(ddof=1) / np.sqrt(len(delta))),
                             ci=[low, high], half_width=(high - low) / 2, accepted=accepted(high),
                             verdict='ACCEPTED' if accepted(high) else 'no detectable improvement',
                             week_block_ci=[float(week_low), float(week_high)],
                             week_block_half_width=float(week_high - week_low) / 2)
    return results, deltas


def metric_records(probs, actual, masks, key=None):
    """One record per (group, model): n, probability_metrics, mean predicted draw and observed draw rate."""
    records = []
    for group, mask in masks:
        for name, p in probs.items():
            p_rows, rows_mask = p
            use = mask[rows_mask] if rows_mask is not None else mask
            values = p_rows[use]
            observed = actual[rows_mask][use] if rows_mask is not None else actual[use]
            if len(values):
                records.append({**({key: group} if key else {}), 'model': MODELS[name], 'n': int(len(values)),
                                **probability_metrics(values, observed),
                                'mean p(draw)': float(values[:, 1].mean()),
                                'observed draw rate': float(np.mean(observed == 1))})
    return pd.DataFrame(records)


# ---------------------------------------------------------------- reports

def table(records, digits=6):
    return harness.markdown_table(pd.DataFrame(records), digits) if len(records) else 'None.'


def fmt(value):
    return f'{value:+.6f}'


def scored_row_records(scored, probs, newcomer):
    """Per scored row: key, goals, newcomer flag and every model's (home, draw, away) probabilities (None if absent)."""
    lookup = {name: (np.arange(len(scored)) if mask is None else np.cumsum(mask) - 1, mask)
              for name, (_, mask) in probs.items()}
    records = []
    for position, row in enumerate(scored.itertuples()):
        record = dict(league=row.competition, season=row.season, datetime=row.date.strftime('%Y-%m-%dT%H:%M:%S'),
                      home=row.team_home, away=row.team_away, goals_home=int(row.goals_home),
                      goals_away=int(row.goals_away), newcomer=bool(newcomer[position]))
        for name, (p, _) in probs.items():
            positions, mask = lookup[name]
            record[name] = None if mask is not None and not mask[position] else \
                [float(v) for v in p[positions[position]]]
        records.append(record)
    return records


def score(date, kind, root=PROJECT_DIR):
    """The pre-registered analysis of one committed snapshot. kind: 'primary' (snapshot 1) or 'cumulative'."""
    require_scorable(date, root)
    prov = provenance(root)
    p1, p2_params, p2_sha = load_models(root)
    history = load_history()
    snapshot, manifest = read_json(snapshot_name(date), root), read_json(manifest_name(date), root)
    live = live_frame(snapshot['rows'])
    names, checks, stops = data_checks(history, live)
    if stops:
        raise SystemExit('STOP: ' + '; '.join(stops))
    forward_keys, forward_info = forward_state()
    both, cast = concatenate(history, live)
    model_rows, equality = forecasts(both, p1, p2_params)
    flagged = sorted(names.loc[names['flagged'], 'team'])
    scored, logged, named = select_scored(both, history, forward_keys, flagged)

    # Scores from here on: L rows only.
    actual = outcome_classes(scored)
    cols = harness.PROB_COLUMNS
    probs = {name: model_rows[name].loc[scored.index, cols].to_numpy(float) for name in ('M0', 'M1', 'M2')}
    loss = {name: harness.row_scores(p, actual)['LogLoss'] for name, p in probs.items()}
    tests, deltas = run_tests(loss, scored['date'])
    h_teams = set(history['team_home']) | set(history['team_away'])
    newcomer = (~scored['team_home'].isin(h_teams) | ~scored['team_away'].isin(h_teams)).to_numpy()
    m3, m3_mask, renormalized = stage1_reference(history, scored)
    m4_all, m4_mask = harness.market_probs(scored)
    m4 = m4_all[m4_mask]
    every = np.ones(len(scored), dtype=bool)
    full = {name: (p, None) for name, p in probs.items()}
    with_refs = dict(full, M3=(m3, m3_mask), M4=(m4, m4_mask))

    overall = metric_records(full, actual, [('all', every)])
    per_league = metric_records(full, actual, [(league, (scored['competition'] == league).to_numpy())
                                               for league in LEAGUES], 'league')
    league_diffs = []
    for league in LEAGUES:
        mask = (scored['competition'] == league).to_numpy()
        if mask.any():
            league_diffs.append({'league': league, 'n': int(mask.sum()),
                                 **{f'{name} mean diff': float(deltas[name][mask].mean()) for name in TESTS}})
    split = metric_records(full, actual, [('newcomer', newcomer), ('established', ~newcomer)], 'matches')
    split_diffs = [{'matches': label, 'n': int(mask.sum()),
                    **{f'{name} mean diff': float(deltas[name][mask].mean()) for name in TESTS}}
                   for label, mask in (('newcomer', newcomer), ('established', ~newcomer)) if mask.any()]
    draws = metric_records(with_refs, actual, [('own rows', every)])[['model', 'n', 'mean p(draw)',
                                                                       'observed draw rate']]
    m3_table = metric_records(dict(full, M3=(m3, m3_mask)), actual, [('M3 rows', m3_mask)])
    m4_table = metric_records(dict(full, M4=(m4, m4_mask)), actual, [('M4 rows', m4_mask)])
    market = m4_table.loc[m4_table['model'] == MODELS['M4']]
    m4_gap = [{'model': MODELS[name], 'n': int(m4_mask.sum()),
               **{f'{metric} gap': float(m4_table.loc[m4_table['model'] == MODELS[name], metric].iloc[0]
                                         - market[metric].iloc[0]) for metric in ('LogLoss', 'RPS', 'Brier')}}
              for name in ('M0', 'M1', 'M2')] if m4_mask.any() else []

    label = LABEL if kind == 'primary' else f'{CUMULATIVE_LABEL}; {LABEL}'
    payload = dict(
        label=label, wording=WORDING, kind=kind, snapshot_date=date, rows_sha256=manifest['rows_sha256'],
        preregistration_commit=git('log', '--format=%H', '--', PREREG, root=root).stdout.split()[0], **prov,
        home_adv=HOME_ADV, p2_frozen_sha256=p2_sha, equality_checks=equality, string_cast_needed=cast,
        counts=dict(snapshot_rows=len(snapshot['rows']), completed=len(live), concatenated=len(both),
                    excluded_forward_log=len(logged), excluded_flagged_names=len(named), test_set=len(scored),
                    newcomer_matches=int(newcomer.sum()), established_matches=int((~newcomer).sum()),
                    m3_rows=int(m3_mask.sum()), m3_renormalized=renormalized, m4_rows=int(m4_mask.sum()),
                    per_league_test={league: int((scored['competition'] == league).sum()) for league in LEAGUES}),
        forward_log=forward_info, data_checks=checks, name_audit=names.to_dict(orient='records'),
        flagged_teams=flagged, club_id_aliases=CLUB_ID_ALIASES, newcomers=sorted(names['team']), market_columns=CLOSING,
        rule=dict(level=LEVEL, seed=SEED, n_resamples=N_RESAMPLES, bootstrap='paired, resampling matches',
                  accept='upper bound below 0'),
        tests=tests, overall=overall.to_dict(orient='records'), per_league=per_league.to_dict(orient='records'),
        per_league_diffs=league_diffs, newcomer_split=split.to_dict(orient='records'), newcomer_split_diffs=split_diffs,
        draws=draws.to_dict(orient='records'), m3=m3_table.to_dict(orient='records'),
        m4=m4_table.to_dict(orient='records'), m4_gap=m4_gap,
        scored_rows=scored_row_records(scored, with_refs, newcomer))
    lines = report_lines(payload, logged, named)
    stem = 'primary' if kind == 'primary' else f'cumulative_{date}'
    write_text(rel(f'{stem}.md'), '\n'.join(lines) + '\n', root)
    write_json(rel(f'{stem}.json'), payload, root)
    print('\n'.join(lines[:40]))
    return payload


def report_lines(payload, logged, named):
    tests, counts = payload['tests'], payload['counts']
    primary = payload['kind'] == 'primary'
    title = LABEL if primary else f'{CUMULATIVE_LABEL} ({LABEL})'
    lines = [f'# {title}', '', f'**{payload["label"]}.** {WORDING}', '']
    if not primary:
        lines += [f'**This is a {CUMULATIVE_LABEL}.** Its intervals are descriptive; the pre-registered verdicts are '
                  'those of `results/live2627/primary.md`.', '']
    lines += [f'Pre-registered in `{PREREG}` (commit {payload["preregistration_commit"]}). Snapshot '
              f'`{snapshot_name(payload["snapshot_date"])}` (rows sha256 {payload["rows_sha256"]}). Code commit '
              f'{payload["code_commit"]}, uncommitted changes when run: {"yes" if payload["code_dirty"] else "no"}. '
              f'home_adv {HOME_ADV!r} (fixed). P2 frozen file self-hash {payload["p2_frozen_sha256"]}.', '',
              'Checks on forecasts only, before any score (tolerance 1e-12):',
              *[f'- {name}: max abs difference {value:.1e} over {counts["concatenated"]} concatenated rows.'
                for name, value in payload['equality_checks'].items()],
              f'- String-dtype cast of L needed for the concatenation: {"yes" if payload["string_cast_needed"] else "no"}.',
              '', '## Rows', '',
              f'- Snapshot rows: {counts["snapshot_rows"]}; completed L rows: {counts["completed"]}.',
              f'- Excluded, in the forward log (matched on league, season, home, away): {counts["excluded_forward_log"]}.',
              *[f'  - {r.competition}: {r.team_home} v {r.team_away}, {r.date:%Y-%m-%d %H:%M}' for r in logged.itertuples()],
              f'- Excluded, flagged name (WRatio 88 or more, or a club_id alias: post-hoc stricter reading, '
              f'DECISIONS.md 2026-10-27): {counts["excluded_flagged_names"]} rows; flagged teams: '
              f'{", ".join(payload["flagged_teams"]) or "none"}; WRatio flags: '
              f'{", ".join(r["team"] for r in payload["name_audit"] if r["flagged_wratio"]) or "none"}; club_id '
              f'aliases: {", ".join(r["team"] + " = " + r["alias_of"] for r in payload["name_audit"] if r["alias_of"]) or "none"}.',
              *[f'  - {r.competition}: {r.team_home} v {r.team_away}, {r.date:%Y-%m-%d %H:%M}' for r in named.itertuples()],
              f'- Test set: {counts["test_set"]} matches; newcomer matches {counts["newcomer_matches"]}, established '
              f'{counts["established_matches"]}.',
              f'- Newcomers (in L, absent from H; kept, cold start): {", ".join(payload["newcomers"]) or "none"}.', '',
              table([{'league': league, 'test rows': n} for league, n in counts['per_league_test'].items()]), '',
              f'## Primary tests ({"pre-registered" if primary else "descriptive, cumulative"})', '',
              'Mean per-match log-loss difference on the test set; 97.5% paired bootstrap CI resampling matches '
              f'(Bonferroni for two tests; 2000 resamples, seed {SEED}). An improvement is accepted only if the upper '
              'bound is below 0.', '',
              '| test | comparison | n | first | second | mean diff | SE | 97.5% CI | half-width | verdict |',
              '|---|---|---|---|---|---|---|---|---|---|',
              *[f'| {name} | {t["comparison"]} | {t["n"]} | {t["first"]:.6f} | {t["second"]:.6f} | '
                f'{fmt(t["mean_delta"])} | {t["se"]:.6f} | [{fmt(t["ci"][0])}, {fmt(t["ci"][1])}] | '
                f'{t["half_width"]:.6f} | {"**" + t["verdict"] + "**" if primary else "descriptive"} |'
                for name, t in tests.items()], '']
    for name, t in tests.items():
        if primary:
            outcome = ('ACCEPTED: an improvement under the pre-registered rule' if t['accepted']
                       else 'no detectable improvement')
            lines.append(f'- {name} ({t["comparison"]}): {outcome}; point estimate {fmt(t["mean_delta"])}, 97.5% CI '
                         f'[{fmt(t["ci"][0])}, {fmt(t["ci"][1])}].')
        else:
            lines.append(f'- {name} ({t["comparison"]}): {fmt(t["mean_delta"])}, 97.5% CI [{fmt(t["ci"][0])}, '
                         f'{fmt(t["ci"][1])}] (descriptive; the verdict stays with snapshot 1).')
    lines += ['', '## Secondary (descriptive, no verdict)', '',
              '### Week-block bootstrap (calendar weeks), 97.5%, 2000 resamples, seed 20261031', '',
              '| test | mean diff | 97.5% week-block CI | half-width |', '|---|---|---|---|',
              *[f'| {name} | {fmt(t["mean_delta"])} | [{fmt(t["week_block_ci"][0])}, {fmt(t["week_block_ci"][1])}] | '
                f'{t["week_block_half_width"]:.6f} |' for name, t in tests.items()], '',
              '### Test set: M0-M2', '', table(payload['overall']), '',
              '### Per league', '', table(payload['per_league']), '',
              '### Per league, mean differences', '', table(payload['per_league_diffs']), '',
              '### Newcomer matches (a team absent from H) and established matches', '',
              table(payload['newcomer_split']), '', table(payload['newcomer_split_diffs']), '',
              '### Draws: mean predicted probability and observed rate (each model on its own rows)', '',
              table(payload['draws']), '',
              f'### M3 Stage 1 static Dixon-Coles on its rows (both teams in H; n={counts["m3_rows"]}; fitted once on '
              f'all H, never updated; renormalized rows {counts["m3_renormalized"]})', '', table(payload['m3']), '',
              f'### M4 closing average ({", ".join(CLOSING)}; overround removed proportionally; n={counts["m4_rows"]} '
              f'of {counts["test_set"]} test rows)', '',
              'Closing odds are later information than any pre-match forecast: benchmark only.', '',
              table(payload['m4']), '', 'Gap, model minus M4 (positive: the market is better):', '',
              table(payload['m4_gap']), '']
    return lines


# ---------------------------------------------------------------- snapshot runs

def take_snapshot(first, root=PROJECT_DIR):
    """Fetch L once and write a new dated snapshot and manifest (and, for the first, the data audit)."""
    failures = preregistration_failures(root)
    if failures:
        raise SystemExit(f'Fetch refused before the committed pre-registration: {failures}')
    date = dt.datetime.now(dt.UTC).strftime('%Y%m%d')
    if os.path.exists(os.path.join(root, snapshot_name(date))):
        raise SystemExit(f'{snapshot_name(date)} exists; a snapshot is never overwritten.')
    prov = provenance(root)
    history = load_history()
    forward_keys, forward_info = forward_state()
    raw, fetched_at = fetch_live()
    rows, non_numeric = snapshot_rows(raw)
    live = live_frame(rows)
    names, checks, stops = data_checks(history, live)
    fetched = raw_frame(rows)
    per_league = {league: dict(fetched=int((fetched['competition'] == league).sum()),
                               completed=checks['per_league'][league]) for league in LEAGUES}
    manifest = dict(snapshot_date=date, fetched_at_utc=forward_logger.iso_utc(fetched_at), source=SOURCE,
                    season=SEASON, per_league=per_league, rows_fetched=len(rows), rows_completed=len(live),
                    earliest_date=f'{live["date"].min():%Y-%m-%d %H:%M}' if len(live) else None,
                    latest_date=f'{live["date"].max():%Y-%m-%d %H:%M}' if len(live) else None,
                    columns_present=sorted(map(str, raw.columns)), snapshot_fields=SNAPSHOT_FIELDS,
                    non_numeric_values=non_numeric, rows_sha256=rows_sha256(rows),
                    preregistration=dict(path=PREREG, commit=git('log', '--format=%H', '--', PREREG,
                                                                 root=root).stdout.split()[0]),
                    forward_log=forward_info, **prov)
    write_text(snapshot_name(date), snapshot_text(date, rows), root)
    write_json(manifest_name(date), manifest, root)
    if rows_sha256(read_json(snapshot_name(date), root)['rows']) != manifest['rows_sha256']:
        raise AssertionError('The written snapshot does not match its manifest hash.')
    if first:
        keys = zip(live['competition'], live['season'], live['team_home'], live['team_away'])
        overlap = live.loc[[key in forward_keys for key in keys]]
        text = audit_text(manifest, live, names, checks, overlap, history)
        write_text(rel('data_audit.md'), text, root)
        print(text)
    print(f'Snapshot {date}: {len(rows)} rows fetched, {len(live)} completed; rows sha256 {manifest["rows_sha256"]}.')
    if stops:
        raise SystemExit('STOP: ' + '; '.join(stops))
    print(f'Commit {snapshot_name(date)} and {manifest_name(date)} before scoring.')
    return date


def audit_text(manifest, live, names, checks, overlap, history):
    """results/live2627/data_audit.md: counts and missing shares only; no outcome is read."""
    records = []
    for league in LEAGUES:
        rows = live.loc[live['competition'] == league]
        sot_missing = rows[SOT].isna().any(axis=1).mean() if len(rows) else float('nan')
        valid = (rows[CLOSING].apply(pd.to_numeric, errors='coerce') > 1.0).all(axis=1)
        records.append({'league': league, 'fetched': manifest['per_league'][league]['fetched'],
                        'completed': len(rows), 'newcomers': checks['newcomers_per_league'][league],
                        'SoT missing': float(sot_missing),
                        'closing avg missing': float(1.0 - valid.mean()) if len(rows) else float('nan'),
                        'first': f'{rows["date"].min():%Y-%m-%d}' if len(rows) else '',
                        'last': f'{rows["date"].max():%Y-%m-%d}' if len(rows) else ''})
    stripped = sorted(t for t in set(live['team_home']) | set(live['team_away']) if t != t.strip())
    lines = [
        '# Live 2026-27 data audit (snapshot 1)', '',
        f'{WORDING}', '',
        'Counts and missing shares only: no outcome metric, no forecast. Rules: `live2627/PREREGISTRATION.md`.', '',
        f'- Source: {manifest["source"]}; fetched {manifest["fetched_at_utc"]}.',
        f'- Snapshot `{snapshot_name(manifest["snapshot_date"])}`: {manifest["rows_fetched"]} rows fetched, '
        f'{manifest["rows_completed"]} completed (goals and datetime present); rows sha256 {manifest["rows_sha256"]}.',
        f'- Completed rows dated {manifest["earliest_date"]} to {manifest["latest_date"]}; last H date '
        f'{history["date"].max():%Y-%m-%d %H:%M}.',
        f'- Non-numeric source values written as null: {manifest["non_numeric_values"]}.', '',
        '## Rows and missing shares per league', '',
        'SoT missing = share of completed rows with hst or ast missing. Closing avg missing = share of completed rows '
        f'without a valid {"/".join(CLOSING)} triple (all three numeric and > 1).', '',
        harness.markdown_table(pd.DataFrame(records), 3), '',
        '## Newcomers and name audit', '',
        f'Newcomers: teams in L absent from every H row (kept, cold start). Best rapidfuzz WRatio against the H names '
        f'of the same league, raw and with `utils.default_process`; flagged if either is {NAME_THRESHOLD} or more '
        f'(rows excluded from the test set; names never merged). STOP above {MAX_NEWCOMERS} newcomers in a league.', '',
        harness.markdown_table(names, 1) if len(names) else 'No newcomers.', '',
        f'- Newcomers: {len(names)}; flagged: {int(names["flagged"].sum()) if len(names) else 0} '
        f'({", ".join(names.loc[names["flagged"], "team"]) if len(names) and names["flagged"].any() else "none"}).',
        '', '## Checks', '',
        f'- Duplicate (league, datetime, home, away) rows: {checks["duplicate_rows"]}.',
        f'- Duplicate (league, season, home, away) pairs: {checks["duplicate_pairs"]}.',
        f'- Team-days with two matches: {checks["team_twice_a_day"]}.',
        f'- Names with leading or trailing spaces: {stripped or "none"}.',
        f'- Overlap with the forward log ({manifest["forward_log"]["rows"]} logged rows): {len(overlap)} completed L '
        'rows, excluded from the test set.',
        *[f'  - {r.competition}: {r.team_home} v {r.team_away}, {r.date:%Y-%m-%d %H:%M}' for r in overlap.itertuples()],
        f'- Columns present in the fetch: {len(manifest["columns_present"])}; SoT columns '
        f'{[c for c in SOT if c in manifest["columns_present"]]}; closing average columns '
        f'{[c for c in CLOSING if c in manifest["columns_present"]]}.', '']
    return '\n'.join(lines)


# ---------------------------------------------------------------- verify

def verify(root=PROJECT_DIR, history=None):
    """Failure messages: pre-registration, snapshot hashes, and that every scored row is an L row."""
    failures = list(preregistration_failures(root))
    dates = snapshot_dates(root)
    if not dates:
        failures.append('no snapshot found')
    for date in dates:
        failures += snapshot_failures(date, root, require_committed=False)
    outputs = [('primary.json', dates[0] if dates else None)] + [
        (os.path.basename(name), os.path.basename(name)[len('cumulative_'):-len('.json')])
        for name in sorted(glob.glob(os.path.join(root, RESULTS, 'cumulative_*.json')))]
    if history is not None:
        h_keys = set(zip(history['competition'], history['season'], history['team_home'], history['team_away'],
                         history['date'].dt.strftime('%Y-%m-%dT%H:%M:%S')))
        last_h = history['date'].max().strftime('%Y-%m-%dT%H:%M:%S')
    for name, date in outputs:
        if not os.path.isfile(os.path.join(root, RESULTS, name)):
            continue
        payload = read_json(rel(name), root)
        if payload.get('snapshot_date') != date or date not in dates:
            failures.append(f'{name}: snapshot_date {payload.get("snapshot_date")} is not snapshot {date}')
            continue
        snapshot_keys = {(r['league'], r['season'], r['home'], r['away'], r['datetime'])
                         for r in read_json(snapshot_name(date), root)['rows']}
        for row in payload.get('scored_rows', []):
            key = (row['league'], row['season'], row['home'], row['away'], row['datetime'])
            if row['season'] != SEASON or key not in snapshot_keys:
                failures.append(f'{name}: scored row {key} is not an L row of snapshot {date}')
            elif history is not None and (key in h_keys or row['datetime'] <= last_h):
                failures.append(f'{name}: scored row {key} is an H (or TEST) row')
        if len(payload.get('scored_rows', [])) != payload.get('counts', {}).get('test_set'):
            failures.append(f'{name}: scored_rows does not list the whole test set')
    return failures


def run_verify():
    history = load_history()
    failures = verify(PROJECT_DIR, history)
    for failure in failures:
        print(f'FAIL {failure}')
    dates = snapshot_dates()
    print(f'VERIFY: {"FAIL" if failures else "PASS"} (pre-registration, {len(dates)} snapshot(s), scored rows)')
    return 1 if failures else 0


# ---------------------------------------------------------------- entry points

def run_primary():
    dates = snapshot_dates()
    if not dates:
        raise SystemExit('No snapshot; run --snapshot first.')
    if os.path.exists(os.path.join(PROJECT_DIR, rel('primary.json'))):
        raise SystemExit('The primary scoring already ran (once only).')
    score(dates[0], 'primary')


def run_refresh():
    dates = snapshot_dates()
    if not dates or not os.path.exists(os.path.join(PROJECT_DIR, rel('primary.json'))):
        raise SystemExit('Run --snapshot and the primary scoring first.')
    latest = dates[-1]
    if latest != dates[0] and not os.path.exists(os.path.join(PROJECT_DIR, rel(f'cumulative_{latest}.json'))):
        score(latest, 'cumulative')
    else:
        take_snapshot(first=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Live 2026-27 evaluation of the frozen models.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--snapshot', action='store_true', help='first fetch: snapshot, manifest and data audit')
    mode.add_argument('--refresh', action='store_true', help='new dated snapshot, or score a committed newer one')
    mode.add_argument('--verify', action='store_true', help='pre-registration, snapshot hashes, no TEST row scored')
    mode.add_argument('--alias-check', action='store_true', help='club_id alias evidence for the newcomers (read only)')
    args = parser.parse_args(argv)
    if args.verify:
        return run_verify()
    if args.alias_check:
        return run_alias_check()
    if args.snapshot:
        if snapshot_dates():
            raise SystemExit('A snapshot exists; later fetches use --refresh.')
        take_snapshot(first=True)
    elif args.refresh:
        run_refresh()
    else:
        run_primary()
    return 0


if __name__ == '__main__':
    sys.exit(main())
