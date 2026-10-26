"""P2 fresh seasons 2014-2015 to 2018-2019: ingestion, cleaning, coverage audit and the F scoring guard.

The fresh frame (F) is its own chronological sequence, cleaned as data_pipeline cleans the main data. The audit
reports counts and missing shares only, never outcomes or forecasts.
"""
import os
import subprocess

import numpy as np
import pandas as pd
import penaltyblog as pb

from data_pipeline import LEAGUES, PROJECT_DIR

FRESH_SEASONS = ['2014-2015', '2015-2016', '2016-2017', '2017-2018', '2018-2019']
BURN_IN_SEASON = '2014-2015'
SCORED_SEASONS = FRESH_SEASONS[1:]
FRESH_PATH = os.path.join(PROJECT_DIR, 'data', 'fixtures_pre2019.pkl')
FROZEN = 'results/p2/candidate_p2.json'
MAX_MISSING_SHARE = 0.10  # more than this share of league-seasons unfetchable: STOP
FETCH_ATTEMPTS = 3
SOT_COLUMNS = ('hst', 'ast')
# Snapshot (non-closing average) triple: avg_* on the main data; the pre-2019 files carry Betbrain averages.
SNAPSHOT_TRIPLE = ('avg_h', 'avg_d', 'avg_a')
SNAPSHOT_FALLBACK = ('bb_av_h', 'bb_av_d', 'bb_av_a')
CLOSING_CHOICES = [(('avg_ch', 'avg_cd', 'avg_ca'), 'closing average'),
                   (('psch', 'pscd', 'psca'), 'Pinnacle closing')]


def fetch_fresh(leagues=LEAGUES, seasons=FRESH_SEASONS):
    """Raw concatenated F frame (league-major, as data_pipeline) and the list of unfetchable league-seasons."""
    frames, failures = [], []
    for league in leagues:
        for season in seasons:
            for attempt in range(1, FETCH_ATTEMPTS + 1):
                try:
                    frames.append(pb.scrapers.FootballData(league, season).get_fixtures())
                    print(f'  fetched {league} {season}')
                    break
                except Exception as error:  # noqa: BLE001 - any failure is recorded, then retried
                    if attempt == FETCH_ATTEMPTS:
                        failures.append((league, season, repr(error)))
                        print(f'  FAILED {league} {season}: {error}')
    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return raw, failures


def no_time_groups(raw):
    """Boolean per row: its league-season has no kickoff time on any row (no Time column in the file)."""
    if 'time' not in raw.columns:
        return pd.Series(True, index=raw.index)
    return raw['time'].isna().groupby([raw['competition'], raw['season']]).transform('all')


def clean_fresh(raw):
    """data_pipeline's cleaning, plus the pre-registered datetime = Date fallback for files without a Time column."""
    seasons = set(raw['season'].unique())
    if not seasons <= set(FRESH_SEASONS):
        raise ValueError(f'Season outside the fresh window: {sorted(seasons - set(FRESH_SEASONS))}')
    df = raw.copy()
    fallback = no_time_groups(df)
    if 'datetime' not in df.columns:
        df['datetime'] = pd.NaT
    df.loc[fallback, 'datetime'] = df.loc[fallback, 'date']
    df = df.dropna(subset=['goals_home', 'goals_away', 'datetime'])
    df['date'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('date').reset_index(drop=True)
    assert_fresh_only(df)
    return df


def assert_fresh_only(df):
    late = sorted(set(df['season']) - set(FRESH_SEASONS))
    if late:
        raise AssertionError(f'Fresh set contains seasons outside 2014-2015 to 2018-2019: {late}')
    if (df['date'] >= pd.Timestamp('2019-07-01')).any():
        raise AssertionError('Fresh set contains a match dated after the 2018-2019 season.')


def load_fresh(path=FRESH_PATH):
    if not os.path.exists(path):
        raise SystemExit(f'No fresh cache at {path}; run python -X utf8 run_p2.py --fetch first.')
    return clean_fresh(pd.read_pickle(path))


def snapshot_columns(frame):
    """The snapshot triple present in a frame: avg_* if present, else the Betbrain average; None if neither."""
    for triple in (SNAPSHOT_TRIPLE, SNAPSHOT_FALLBACK):
        if set(triple) <= set(frame.columns) and frame[list(triple)].notna().any().any():
            return triple
    return None


def valid_triple(frame, triple):
    """Rows whose three odds are numeric and > 1."""
    if triple is None or not set(triple) <= set(frame.columns):
        return pd.Series(False, index=frame.index)
    numeric = frame[list(triple)].apply(pd.to_numeric, errors='coerce')
    return (numeric > 1.0).all(axis=1)


def snapshot_odds(frame):
    """Snapshot odds (n, 3) per row, from avg_* or, per league-season without avg_*, the Betbrain average."""
    odds = np.full((len(frame), 3), np.nan)
    columns = pd.Series('', index=frame.index, dtype=object)
    for _, ids in frame.groupby(['competition', 'season']).groups.items():
        group = frame.loc[ids]
        triple = snapshot_columns(group)
        if triple is None:
            continue
        mask = valid_triple(group, triple).to_numpy()
        positions = frame.index.get_indexer(ids)[mask]
        odds[positions] = group[list(triple)].apply(pd.to_numeric, errors='coerce').to_numpy()[mask]
        columns.iloc[positions] = '/'.join(triple)
    return odds, columns


def require_frozen(root=PROJECT_DIR):
    """Raises unless results/p2/candidate_p2.json exists, is tracked, and has no uncommitted change."""
    path = os.path.join(root, FROZEN)
    if not os.path.isfile(path):
        raise RuntimeError(f'F scoring refused: {FROZEN} does not exist.')

    def git(*args):
        return subprocess.run(['git', *args], cwd=root, capture_output=True, text=True).returncode

    if git('ls-files', '--error-unmatch', FROZEN) != 0:
        raise RuntimeError(f'F scoring refused: {FROZEN} is not committed.')
    if git('diff', '--quiet', 'HEAD', '--', FROZEN) != 0:
        raise RuntimeError(f'F scoring refused: {FROZEN} differs from the committed version.')
    return path


def fresh_scoring_rows(fresh, root=PROJECT_DIR):
    """The only way to obtain scorable F rows: the scored seasons, after the frozen-file guard."""
    require_frozen(root)
    assert_fresh_only(fresh)
    return fresh.loc[fresh['season'].isin(SCORED_SEASONS)]


def audit(raw, failures, fresh):
    """Counts and missing shares only (results/p2/data_audit.md); no outcome is read."""
    import exp_harness as harness

    groups = [(league, season) for league in LEAGUES for season in FRESH_SEASONS]
    fallback = no_time_groups(raw)
    records = []
    for league, season in groups:
        raw_rows = raw.loc[(raw.competition == league) & (raw.season == season)] if len(raw) else raw
        rows = fresh.loc[(fresh.competition == league) & (fresh.season == season)]
        if not len(raw_rows):
            records.append({'league season': f'{league} {season}', 'raw rows': 0, 'clean rows': 0})
            continue
        sot_missing = rows[list(SOT_COLUMNS)].isna().any(axis=1).mean() if set(SOT_COLUMNS) <= set(rows) else 1.0
        triple = snapshot_columns(rows)
        record = {'league season': f'{league} {season}', 'raw rows': len(raw_rows), 'clean rows': len(rows),
                  'datetime = Date': bool(fallback.loc[raw_rows.index].all()),
                  'SoT missing': float(sot_missing),
                  'snapshot cols': '/'.join(triple) if triple else 'none',
                  'snapshot missing': 1.0 - float(valid_triple(rows, triple).mean())}
        for closing, label in CLOSING_CHOICES:
            record[f'{label} missing'] = 1.0 - float(valid_triple(rows, closing).mean())
        records.append(record)
    table = pd.DataFrame(records)

    odds_like = [c for c in raw.columns if c not in harness.NON_ODDS_COLUMNS and c not in ('id', 'time')]
    closing_named = {c for triple in harness.CLOSING_TRIPLES for c in triple} | {c for c in harness.CLOSING_OTHER}
    teams = pd.concat([fresh[['competition', 'team_home']].rename(columns={'team_home': 'team'}),
                       fresh[['competition', 'team_away']].rename(columns={'team_away': 'team'})])
    leagues_per_team = teams.drop_duplicates().groupby('team').competition.nunique()
    stripped = sorted(t for t in teams.team.unique() if str(t) != str(t).strip())
    per_day = pd.concat([fresh[['date', 'team_home']].rename(columns={'team_home': 'team'}),
                         fresh[['date', 'team_away']].rename(columns={'team_away': 'team'})])
    twice = per_day.assign(day=per_day.date.dt.normalize()).duplicated(['day', 'team']).sum()
    team_counts = (teams.drop_duplicates().groupby('competition').team.nunique())
    per_season = pd.concat([fresh[['competition', 'season', 'team_home']].rename(columns={'team_home': 'team'}),
                            fresh[['competition', 'season', 'team_away']].rename(columns={'team_away': 'team'})])
    teams_per_ls = per_season.drop_duplicates().groupby(['competition', 'season']).team.nunique()
    missing_groups = len(failures)
    lines = [
        '# P2 fresh data audit (2014-2015 to 2018-2019)', '',
        'Counts and missing shares only: no outcome metric, no forecast. Source: penaltyblog FootballData '
        f'(football-data.co.uk), fetched fresh; raw cache `data/fixtures_pre2019.pkl` (not committed).', '',
        f'- League-seasons requested: {len(groups)}; fetched: {len(groups) - missing_groups}; '
        f'not fetchable: {missing_groups} ({missing_groups / len(groups):.1%}; STOP above 10%).',
        *[f'  - {league} {season}: {error}' for league, season, error in failures],
        f'- Raw rows: {len(raw)}; clean rows (data_pipeline cleaning + datetime fallback): {len(fresh)}; '
        f'2014-2015 burn-in rows: {int((fresh.season == BURN_IN_SEASON).sum())}; scored rows (2015-2016 to '
        f'2018-2019): {int(fresh.season.isin(SCORED_SEASONS).sum())}.',
        f'- Date range: {fresh.date.min():%Y-%m-%d} to {fresh.date.max():%Y-%m-%d}. Seasons present: '
        f'{sorted(fresh.season.unique())}.',
        f'- League-seasons using the pre-registered datetime = Date fallback (no Time column): '
        f'{int(table.get("datetime = Date", pd.Series(dtype=bool)).fillna(False).sum())} of {len(table)}.', '',
        '## Rows and missing shares per league-season', '',
        'SoT missing = share of rows with hst or ast missing. Snapshot missing = share of rows without a valid '
        'snapshot triple (all three odds numeric and > 1). Closing columns are evaluation-only.', '',
        harness.markdown_table(table, 3), '',
        '## Column names', '',
        f'- Shots on target: {", ".join(f"`{c}`" for c in SOT_COLUMNS if c in raw.columns) or "none"} '
        '(home, away).',
        f'- Snapshot triple on F: '
        f'{", ".join(sorted(set(table.get("snapshot cols", pd.Series(dtype=object)).dropna()))) or "none"}.',
        f'- Non-closing odds-like columns: '
        f'{", ".join(f"`{c}`" for c in odds_like if c not in closing_named)}.',
        f'- Closing odds-like columns: {", ".join(f"`{c}`" for c in odds_like if c in closing_named) or "none"}.',
        '',
        '## Team names', '',
        f'- Unique teams per league: {team_counts.to_dict()}.',
        f'- Teams per league-season: min {int(teams_per_ls.min())}, max {int(teams_per_ls.max())}.',
        f'- Teams appearing in more than one league: {sorted(leagues_per_team[leagues_per_team > 1].index) or "none"}.',
        f'- Names with leading or trailing spaces: {stripped or "none"}.',
        f'- Team-days with two matches (would break same-day ordering): {int(twice)}.', '']
    return '\n'.join(lines), missing_groups / len(groups)
