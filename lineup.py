"""Lineup-strength features from Transfermarkt starting XIs, the Gate B estimation on
training data, and (only if Gate B passes) the test-period adjustments file that
main.py --lineup feeds to prepare_lineup_offsets.

Run: python -X utf8 lineup.py  (uses the data/ cache only; never downloads)."""
import argparse
import contextlib
import io
import json
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm

from data_pipeline import LEAGUES, SEASONS, chronological_split, ingest_and_clean_fixtures
from metrics import outcome_classes, probability_metrics
from stage2_dynamic import compute_home_adv
from stage3_detector import (LINEUP_DELTA_LIMIT, PREDICTION_LEAD_MINUTES,
                             load_lineup_adjustments, prepare_lineup_offsets, run_change_filter)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_DIR, 'data')
OUTPUT_DIR = os.path.join(PROJECT_DIR, 'outputs')
ADJUSTMENTS_PATH = os.path.join(OUTPUT_DIR, 'lineup_adjustments.csv')
PLACEBO_PATH = os.path.join(OUTPUT_DIR, 'lineup_adjustments_placebo.csv')
SUMMARY_PATH = os.path.join(OUTPUT_DIR, 'gate_b_summary.txt')
COEFFICIENTS_PATH = os.path.join(OUTPUT_DIR, 'gate_b_coefficients.json')
ATTACK_ONLY_PATH = os.path.join(OUTPUT_DIR, 'lineup_adjustments_attack_only.csv')
ATTACK_ONLY_PLACEBO_PATH = os.path.join(OUTPUT_DIR, 'lineup_adjustments_attack_only_placebo.csv')
EXPLORATORY_LABEL = ('EXPLORATORY (post-hoc, attack-only; chosen after Gate B failed, '
                     'from training data only)')
# Gate B primary c_att to 4 dp; guards against a stale or re-estimated coefficients file.
FROZEN_C_ATT = 0.0950

# Only the columns the features need; players.* is never read.
TABLE_COLUMNS = {
    'clubs': None,
    'competitions': None,
    'games': None,
    'game_lineups': ['game_id', 'club_id', 'player_id', 'type', 'position'],
    'player_valuations': ['player_id', 'date', 'market_value_in_eur'],
}
DEFENCE_POSITIONS = ('Goalkeeper', 'Centre-Back', 'Right-Back', 'Left-Back', 'Defender', 'Sweeper')
ATTACK_POSITIONS = ('Defensive Midfield', 'Central Midfield', 'Attacking Midfield',
                    'Right Midfield', 'Left Midfield', 'Midfield', 'Left Winger', 'Right Winger',
                    'Centre-Forward', 'Second Striker', 'Attack')
POSITION_LINE = {**{p.strip().casefold(): 'defence' for p in DEFENCE_POSITIONS},
                 **{p.strip().casefold(): 'attack' for p in ATTACK_POSITIONS}}

STARTERS_PER_SIDE = 11
ESTIMATION_LEAD = pd.Timedelta(hours=24)
MIN_PRIOR_APPEARANCES = 10
RATE_BOUNDS = (0.15, 6.0)
FEATURE_CLIP = 1.0
USUAL_WINDOW, USUAL_MIN = 10, 5
FALLBACK_QUANTILE = 0.05
PLACEBO_SEED = 20261019
MIN_TEST_COVERAGE = 0.90
EFFECT_COLUMNS = ['home_attack_delta', 'home_defence_delta', 'away_attack_delta', 'away_defence_delta']
# Stage 2 on the 3545 common test rows (Step 0 regression anchors).
BASELINE_ANCHORS = {'RPS': 0.2060203, 'LogLoss': 1.0056991}
ANCHOR_TOLERANCE = 5e-8
TOTAL_FIXTURES, TEST_FIXTURES, COMMON_TEST_FIXTURES = 19145, 3829, 3545


def estimation_cutoff(test_start):
    return test_start - ESTIMATION_LEAD


def load_local_tables(data_dir=DATA_DIR):
    """Reads the Transfermarkt tables already in data/. Never downloads
    (lineup_audit.load_transfermarkt_tables re-downloads on every call)."""
    tables = {}
    for name, columns in TABLE_COLUMNS.items():
        path = os.path.join(data_dir, f'{name}.csv.gz')
        if not os.path.exists(path):
            raise FileNotFoundError(f'{path} is missing; copy data/ from the main checkout.')
        tables[name] = pd.read_csv(path, compression='gzip', low_memory=False, usecols=columns)
    return tables


def link_fixtures(df, tables):
    """tm_game_id from the unchanged audit; home/away club IDs and day from games."""
    from lineup_audit import LEAGUE_IDS, build_lineup_audit
    fixtures, _ = build_lineup_audit(df, LEAGUE_IDS, LEAGUES, SEASONS, [], tables=tables)
    if not fixtures.index.equals(df.index):
        raise ValueError('Audit fixtures.index differs from df.index.')
    games = tables['games'][['game_id', 'home_club_id', 'away_club_id', 'date']].copy()
    games['game_id'] = pd.to_numeric(games['game_id'], errors='coerce')
    games = games.dropna(subset=['game_id'])
    games['tm_day'] = pd.to_datetime(games['date'], errors='coerce').dt.normalize()
    links = pd.DataFrame({'tm_game_id': fixtures['tm_game_id']}, index=df.index)
    for column in ('home_club_id', 'away_club_id'):
        lookup = dict(zip(games['game_id'].astype('int64'), games[column]))
        links[column] = pd.to_numeric(links['tm_game_id'].map(lookup), errors='coerce').astype('Int64')
    links['tm_day'] = pd.to_datetime(links['tm_game_id'].map(
        dict(zip(games['game_id'].astype('int64'), games['tm_day']))))
    matched = links['tm_game_id'].notna()
    if links.loc[matched, ['home_club_id', 'away_club_id', 'tm_day']].isna().any().any():
        raise ValueError('A matched fixture lacks club IDs or a date in games.')
    return links


def map_positions(positions):
    """strip + casefold, exact match; anything else (including NaN) maps to NaN."""
    cleaned = pd.Series(positions, dtype='object').map(
        lambda p: p.strip().casefold() if isinstance(p, str) else None)
    return cleaned.map(POSITION_LINE)


def starting_xi(game_lineups, links):
    """Starters for every linked side, plus one status row per (row_id, side).

    A side is usable ('ok') only with exactly 11 starting_lineup rows, 11 distinct
    players, and every position mapped to a line. Substitutes are never read."""
    starters = game_lineups.loc[game_lineups['type'] == 'starting_lineup',
                                ['game_id', 'club_id', 'player_id', 'position']]
    starters = starters.astype({'game_id': 'int64', 'club_id': 'int64', 'player_id': 'int64'})
    linked = links.loc[links['tm_game_id'].notna()]
    keys = pd.concat([
        pd.DataFrame({'row_id': linked.index.to_numpy(), 'side': side,
                      'game_id': linked['tm_game_id'].astype('int64').to_numpy(),
                      'club_id': linked[f'{side}_club_id'].astype('int64').to_numpy()})
        for side in ('home', 'away')], ignore_index=True)
    rows = keys.merge(starters, on=['game_id', 'club_id'], how='inner')
    print('Starting-lineup position values on linked sides (before mapping):')
    print(rows['position'].value_counts(dropna=False).to_string())
    rows['line'] = map_positions(rows['position']).to_numpy()
    rows['unmapped'] = rows['line'].isna()

    index = pd.MultiIndex.from_product([links.index, ['home', 'away']], names=['row_id', 'side'])
    counts = rows.groupby(['row_id', 'side']).agg(
        n_rows=('player_id', 'size'), n_players=('player_id', 'nunique'),
        n_unmapped=('unmapped', 'sum')).reindex(index, fill_value=0)
    matched = links['tm_game_id'].notna().to_numpy().repeat(2)
    wrong_count = ((counts['n_rows'] != STARTERS_PER_SIDE)
                   | (counts['n_players'] != STARTERS_PER_SIDE)).to_numpy()
    reason = np.select([~matched, wrong_count, counts['n_unmapped'].to_numpy() > 0],
                       ['unmatched', 'starter_count', 'position'], default='ok')
    status = counts.assign(reason=reason)
    rows = rows.join(status['reason'], on=['row_id', 'side'])
    rows = rows.loc[rows['reason'] == 'ok'].drop(columns=['reason', 'unmapped'])
    return rows.reset_index(drop=True), status


def attach_valuations(starters, valuations):
    """Each starter's last valuation strictly before match_day (NaN if none or <= 0)."""
    left = pd.DataFrame({'_row': np.arange(len(starters)),
                         'player_id': starters['player_id'].astype('int64').to_numpy(),
                         'match_day': pd.to_datetime(starters['match_day']).astype('datetime64[ns]').to_numpy()})
    right = pd.DataFrame({'player_id': valuations['player_id'].astype('int64').to_numpy(),
                          'valuation_date': pd.to_datetime(valuations['date']).astype('datetime64[ns]').to_numpy(),
                          'valuation': valuations['market_value_in_eur'].to_numpy(float)})
    merged = pd.merge_asof(left.sort_values('match_day', kind='stable'),
                           right.sort_values('valuation_date', kind='stable'),
                           left_on='match_day', right_on='valuation_date', by='player_id',
                           allow_exact_matches=False, direction='backward')
    merged = merged.sort_values('_row').reset_index(drop=True)
    if not (merged['valuation_date'].isna() | (merged['valuation_date'] < merged['match_day'])).all():
        raise ValueError('A valuation on or after the match day was attached.')
    value = merged['valuation'].to_numpy(float, copy=True)
    value[~(value > 0)] = np.nan
    return starters.assign(valuation_date=merged['valuation_date'].to_numpy(), value=value)


def fallback_value(valuations, cutoff):
    """5th percentile of positive valuations dated strictly before the cutoff's calendar day."""
    dates = pd.to_datetime(valuations['date'])
    values = valuations['market_value_in_eur'].astype(float)
    pool = values[(dates < cutoff.normalize()) & (values > 0)]
    return float(np.quantile(pool, FALLBACK_QUANTILE))


def value_starters(df, links, tables):
    """Usable starting XIs with pre-match valuations; returns (valued starters, side status)."""
    starters, status = starting_xi(tables['game_lineups'], links)
    df_day = df['date'].dt.normalize().astype('datetime64[ns]')
    tm_day = links['tm_day'].astype('datetime64[ns]')
    # The earlier of the two days: can only exclude valuations, never admit a later one.
    match_day = pd.concat([df_day, tm_day], axis=1).min(axis=1)
    differs = tm_day.notna() & (tm_day != df_day)
    print(f'Fixtures whose Transfermarkt day differs from the fixture day: {int(differs.sum())} '
          '(the earlier day is used for valuations)')
    starters = starters.assign(match_day=starters['row_id'].map(match_day).to_numpy())
    return attach_valuations(starters, tables['player_valuations']), status


def side_values(valued, fallback):
    """Attack-line and defence-line value sums per (row_id, side); missing values use F."""
    v = valued.assign(is_fallback=valued['value'].isna(), used=valued['value'].fillna(fallback))
    keys = ['row_id', 'side']
    sides = v.groupby(keys).agg(n_fallback=('is_fallback', 'sum'))
    for line in ('attack', 'defence'):
        sides[f'{line}_value'] = (v.loc[v['line'] == line].groupby(keys)['used'].sum()
                                  .reindex(sides.index, fill_value=0.0))
    return sides


def usual_values(sides, kickoffs):
    """Mean of the club's previous 10 complete sides (strictly earlier kickoff), needing 5."""
    s = sides.reset_index()
    s['kickoff'] = s['row_id'].map(kickoffs).to_numpy()
    s = s.sort_values(['club_id', 'kickoff'], kind='stable')
    if (s.groupby('club_id')['kickoff'].diff() <= pd.Timedelta(0)).any():
        raise ValueError('A club has two fixtures at the same kickoff.')
    for line in ('attack', 'defence'):
        s[f'usual_{line}'] = s.groupby('club_id')[f'{line}_value'].transform(
            lambda x: x.shift(1).rolling(USUAL_WINDOW, min_periods=USUAL_MIN).mean())
    return s.set_index(['row_id', 'side'])[['usual_attack', 'usual_defence']]


def build_features(df, links, valued, status, fallback):
    """Per fixture: A and D for each side, clipped log ratios against the club's usual."""
    sides = side_values(valued, fallback).reset_index()
    home = (sides['side'] == 'home').to_numpy()
    sides['club_id'] = np.where(home,
                                sides['row_id'].map(links['home_club_id']).astype('int64'),
                                sides['row_id'].map(links['away_club_id']).astype('int64'))
    sides = sides.set_index(['row_id', 'side'])
    has_lines = (sides['attack_value'] > 0) & (sides['defence_value'] > 0)
    sides = sides.join(usual_values(sides.loc[has_lines], df['date']))

    full = status[['reason']].join(sides[['n_fallback', 'attack_value', 'defence_value',
                                          'usual_attack', 'usual_defence']])
    xi_ok = full['reason'] == 'ok'
    full.loc[xi_ok & ~((full['attack_value'] > 0) & (full['defence_value'] > 0)), 'reason'] = 'empty_line'
    full.loc[(full['reason'] == 'ok')
             & (full['usual_attack'].isna() | full['usual_defence'].isna()), 'reason'] = 'no_usual'
    full['complete'] = full['reason'] == 'ok'
    full['A_raw'] = np.where(full['complete'], np.log(full['attack_value'] / full['usual_attack']), np.nan)
    full['D_raw'] = np.where(full['complete'], np.log(full['defence_value'] / full['usual_defence']), np.nan)

    features = pd.DataFrame(index=df.index)
    for side in ('home', 'away'):
        part = full.xs(side, level='side').reindex(df.index)
        features[f'A_{side}'] = part['A_raw'].clip(-FEATURE_CLIP, FEATURE_CLIP)
        features[f'D_{side}'] = part['D_raw'].clip(-FEATURE_CLIP, FEATURE_CLIP)
        features[f'A_raw_{side}'] = part['A_raw']
        features[f'D_raw_{side}'] = part['D_raw']
        features[f'n_fallback_{side}'] = part['n_fallback']
        features[f'complete_{side}'] = part['complete'].fillna(False).astype(bool)
        features[f'reason_{side}'] = part['reason']
    return features


def report_features(features, mask, label):
    rows = features.loc[mask]
    complete = rows['complete_home'] & rows['complete_away']
    print(f'{label}: {len(rows)} fixtures')
    print(f'  Complete features on both sides: {int(complete.sum())} ({complete.mean():.2%})')
    reasons = pd.concat([rows['reason_home'], rows['reason_away']]).value_counts()
    print('  Side status: ' + ', '.join(f'{k}={v}' for k, v in reasons.items()))
    n_fb = pd.concat([rows['n_fallback_home'], rows['n_fallback_away']]).dropna()
    total = STARTERS_PER_SIDE * len(n_fb)
    print(f'  Starters using fallback F: {int(n_fb.sum())}/{total} ({n_fb.sum()/max(total, 1):.2%})')
    for name in ('A', 'D'):
        raw = pd.concat([rows.loc[complete, f'{name}_raw_home'], rows.loc[complete, f'{name}_raw_away']])
        value = raw.clip(-FEATURE_CLIP, FEATURE_CLIP)
        print(f'  {name} (both sides pooled, N={len(raw)}): mean={value.mean():.4f}, std={value.std():.4f}, '
              f'p1={value.quantile(.01):.4f}, p99={value.quantile(.99):.4f}, '
              f'clipped={(raw.abs() > FEATURE_CLIP).mean():.2%}')


def prior_appearances(df):
    """Appearances of each side's team in the full frame with a strictly earlier kickoff."""
    long = pd.concat([
        pd.DataFrame({'row_id': df.index.to_numpy(), 'side': side,
                      'team': df[f'team_{side}'].to_numpy(), 'date': df['date'].to_numpy()})
        for side in ('home', 'away')], ignore_index=True)
    if long.duplicated(['team', 'date']).any():
        raise ValueError('A team has two fixtures at the same kickoff.')
    long = long.sort_values('date', kind='stable')
    long['prior'] = long.groupby('team').cumcount()
    wide = long.pivot(index='row_id', columns='side', values='prior').reindex(df.index)
    return wide.rename(columns={'home': 'home_prior', 'away': 'away_prior'})[['home_prior', 'away_prior']]


def burn_in_keep(df, rates, appearances, window):
    """Estimation-only burn-in filter; prints rows dropped per season within `window`."""
    few = (appearances['home_prior'] < MIN_PRIOR_APPEARANCES) | (appearances['away_prior'] < MIN_PRIOR_APPEARANCES)
    low, high = RATE_BOUNDS
    bad_rate = ~(rates['lambda_home'].between(low, high) & rates['mu_away'].between(low, high))
    keep = ~(few | bad_rate)
    table = pd.DataFrame({'season': df['season'], 'rows': 1, 'few_appearances': few,
                          'rate_out_of_bounds': bad_rate, 'dropped': ~keep}).loc[window]
    print('Burn-in filter (estimation window), rows dropped per season:')
    print(table.groupby('season')[['rows', 'few_appearances', 'rate_out_of_bounds', 'dropped']]
          .sum().to_string())
    print(f'  Total dropped: {int(table["dropped"].sum())}/{len(table)}')
    return keep


def estimation_rows(df, features, rates, keep, cutoff):
    """Two Poisson rows per estimation match (home and away goals), dated before the cutoff."""
    selected = ((df['date'] < cutoff) & keep
                & features['complete_home'] & features['complete_away'])
    m, f, r = df.loc[selected], features.loc[selected], rates.loc[selected]
    has_fallback = ((f['n_fallback_home'] > 0) | (f['n_fallback_away'] > 0)).to_numpy()
    home = pd.DataFrame({'match_id': m.index.to_numpy(), 'date': m['date'].to_numpy(),
                         'y': m['goals_home'].to_numpy(float),
                         'offset': np.log(r['lambda_home'].to_numpy(float)),
                         'A_own': f['A_home'].to_numpy(), 'D_opp': f['D_away'].to_numpy(),
                         'has_fallback': has_fallback})
    away = pd.DataFrame({'match_id': m.index.to_numpy(), 'date': m['date'].to_numpy(),
                         'y': m['goals_away'].to_numpy(float),
                         'offset': np.log(r['mu_away'].to_numpy(float)),
                         'A_own': f['A_away'].to_numpy(), 'D_opp': f['D_home'].to_numpy(),
                         'has_fallback': has_fallback})
    rows = pd.concat([home, away], ignore_index=True)
    if (rows['date'] >= cutoff).any():
        raise ValueError('An estimation row is dated on or after ESTIMATION_CUTOFF.')
    if rows[['y', 'offset', 'A_own', 'D_opp']].isna().any().any():
        raise ValueError('Estimation rows contain NaN.')
    return rows


def fit_gate_b(rows):
    exog = sm.add_constant(rows[['A_own', 'D_opp']].astype(float))
    model = sm.GLM(rows['y'].astype(float), exog,
                   family=sm.families.Poisson(link=sm.families.links.Log()),
                   offset=rows['offset'].astype(float))
    return model.fit(cov_type='cluster', cov_kwds={'groups': rows['match_id'].to_numpy()})


def gate_b_numbers(result, rows):
    ci = result.conf_int(alpha=0.05)
    numbers = dict(n_rows=int(len(rows)), n_matches=int(rows['match_id'].nunique()),
                   intercept=float(result.params['const']))
    for key, name in (('att', 'A_own'), ('def', 'D_opp')):
        numbers[f'c_{key}'] = float(result.params[name])
        numbers[f'se_{key}'] = float(result.bse[name])
        numbers[f'ci_{key}'] = [float(ci.loc[name, 0]), float(ci.loc[name, 1])]
    return numbers


def gate_b_verdict(c_att, c_def, ci_att, ci_def):
    """(passed, reason). Passes only with c_att > 0, c_def < 0 and both 95% CIs excluding zero."""
    reasons = []
    if not c_att > 0:
        reasons.append(f'c_att={c_att:.5f} is not > 0')
    if not c_def < 0:
        reasons.append(f'c_def={c_def:.5f} is not < 0')
    for name, (low, high) in (('c_att', ci_att), ('c_def', ci_def)):
        if low <= 0 <= high:
            reasons.append(f'{name} 95% CI [{low:.5f}, {high:.5f}] includes zero')
    if reasons:
        return False, '; '.join(reasons)
    return True, 'c_att > 0, c_def < 0, and both 95% CIs exclude zero'


def describe_fit(label, numbers, primary=None):
    text = (f"{label}: rows={numbers['n_rows']} matches={numbers['n_matches']}; "
            f"c_att={numbers['c_att']:.5f} (SE {numbers['se_att']:.5f}, "
            f"CI [{numbers['ci_att'][0]:.5f}, {numbers['ci_att'][1]:.5f}]); "
            f"c_def={numbers['c_def']:.5f} (SE {numbers['se_def']:.5f}, "
            f"CI [{numbers['ci_def'][0]:.5f}, {numbers['ci_def'][1]:.5f}])")
    notes = []
    for key in ('att', 'def'):
        low, high = numbers[f'ci_{key}']
        if primary is not None and np.sign(numbers[f'c_{key}']) != np.sign(primary[f'c_{key}']):
            notes.append(f'c_{key} sign flips vs primary')
        if low <= 0 <= high:
            notes.append(f'c_{key} CI crosses zero')
    return text + ('  [' + '; '.join(notes) + ']' if notes else '')


def build_adjustments(df, features, test_index, test_start, cutoff, c_att, c_def):
    """Frozen-coefficient deltas for TEST_INDEX fixtures with complete features on both sides."""
    covered = (features.index.isin(test_index)
               & features['complete_home'] & features['complete_away'])
    f, m = features.loc[covered], df.loc[covered]
    limit = LINEUP_DELTA_LIMIT
    return pd.DataFrame({
        'date': m['date'], 'competition': m['competition'],
        'team_home': m['team_home'], 'team_away': m['team_away'],
        'available_at': m['date'] - pd.Timedelta(minutes=PREDICTION_LEAD_MINUTES),
        'ratings_asof': cutoff,
        'home_attack_delta': np.clip(c_att * f['A_home'], -limit, limit),
        'home_defence_delta': np.clip(c_def * f['D_home'], -limit, limit),
        'away_attack_delta': np.clip(c_att * f['A_away'], -limit, limit),
        'away_defence_delta': np.clip(c_def * f['D_away'], -limit, limit),
    }, index=f.index)


def validate_adjustments(adjustments, test_index, test_start, expected_rows):
    if not adjustments.index.isin(test_index).all():
        raise ValueError('Adjustment row outside TEST_INDEX.')
    if (adjustments['date'] < test_start).any():
        raise ValueError('Adjustment row dated before TEST_START.')
    if not (adjustments['available_at'] < adjustments['date']).all():
        raise ValueError('available_at must be strictly before date.')
    if not (adjustments['ratings_asof'] < test_start).all():
        raise ValueError('ratings_asof must precede TEST_START.')
    if adjustments.isna().any().any():
        raise ValueError('Adjustments contain NaN.')
    if adjustments.duplicated(['team_home', 'team_away', 'date']).any():
        raise ValueError('Duplicate (team_home, team_away, date) key.')
    if (adjustments[EFFECT_COLUMNS].abs() > LINEUP_DELTA_LIMIT).any().any():
        raise ValueError('|delta| exceeds LINEUP_DELTA_LIMIT.')
    if len(adjustments) != expected_rows:
        raise ValueError(f'{len(adjustments)} adjustment rows; expected {expected_rows}.')


def placebo_adjustments(adjustments, seed=PLACEBO_SEED):
    """One permutation of whole delta rows across covered fixtures (the four deltas stay together)."""
    permutation = np.random.default_rng(seed).permutation(len(adjustments))
    placebo = adjustments.copy()
    placebo[EFFECT_COLUMNS] = adjustments[EFFECT_COLUMNS].to_numpy()[permutation]
    return placebo


def frozen_attack_coefficient(path=COEFFICIENTS_PATH):
    """c_att from the Gate B primary fit (training data only), never re-estimated."""
    with open(path, encoding='utf-8') as handle:
        coefficients = json.load(handle)
    c_att = float(coefficients['c_att'])
    if coefficients['verdict'] != 'FAILED' or round(c_att, 4) != FROZEN_C_ATT:
        raise ValueError(f'{path} is not the Gate B primary fit (verdict FAILED, c_att {FROZEN_C_ATT}).')
    return c_att


def save_adjustments(df, features, test_index, test_start, cutoff, c_att, c_def, paths, label=''):
    """Coverage rule, frozen-coefficient deltas, asserts, one placebo, and a round trip
    through main.py's loader. paths = (adjustments, placebo). False if coverage < 90%."""
    prefix = f'{label} ' if label else ''
    test_window = df.index.isin(test_index)
    covered = features['complete_home'] & features['complete_away']
    test_coverage = covered[test_window].mean()
    if test_coverage < MIN_TEST_COVERAGE:
        print(f'{prefix}Test-window complete-feature coverage {test_coverage:.2%} < 90%: stopping before evaluation.')
        return False
    expected_rows = int(covered[test_window].sum())
    adjustments = build_adjustments(df, features, test_index, test_start, cutoff, c_att, c_def)
    validate_adjustments(adjustments, test_index, test_start, expected_rows)
    placebo = placebo_adjustments(adjustments)
    validate_adjustments(placebo, test_index, test_start, expected_rows)
    for path, table in zip(paths, (adjustments, placebo)):
        table.to_csv(path, index=False)
        # Round trip through main.py's loader: every row must land on its own fixture.
        offsets = prepare_lineup_offsets(df, load_lineup_adjustments(path))
        if not offsets.index[offsets['lineup_available']].equals(table.index):
            raise ValueError(f'{path} did not round-trip onto the same fixtures.')
        np.testing.assert_allclose(offsets.loc[table.index, EFFECT_COLUMNS].to_numpy(),
                                   table[EFFECT_COLUMNS].to_numpy(), rtol=0, atol=1e-12)
        print(f'{prefix}Wrote {len(table)} rows to {os.path.relpath(path, PROJECT_DIR)}')
    print(f'{prefix}Test coverage: {expected_rows}/{len(test_index)} ({test_coverage:.2%}).')
    return True


def assert_baseline_anchors(metrics):
    for name, anchor in BASELINE_ANCHORS.items():
        if abs(float(metrics[name]) - anchor) >= ANCHOR_TOLERANCE:
            raise ValueError(f'Stage 2 {name} {float(metrics[name]):.7f} differs from anchor {anchor}.')


class _Tee(io.TextIOBase):
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            stream.write(text)
        return len(text)

    def flush(self):
        for stream in self.streams:
            stream.flush()


def main():
    df = ingest_and_clean_fixtures([], refresh=False)
    train_df, test_df = chronological_split(df)
    TEST_INDEX = test_df.index
    TEST_START = test_df['date'].min()
    ESTIMATION_CUTOFF = estimation_cutoff(TEST_START)
    if len(df) != TOTAL_FIXTURES or len(TEST_INDEX) != TEST_FIXTURES:
        raise ValueError(f'Unexpected frame sizes: {len(df)} fixtures, {len(TEST_INDEX)} test rows.')

    # Stage 2 baseline rates from the same call main.py uses (no lineup, change_scale 0).
    home_adv = compute_home_adv(train_df, test_df)
    rates, _ = run_change_filter(df, 0.0, home_adv=home_adv)
    rates = rates.loc[df.index]
    known = set(train_df['team_home']) | set(train_df['team_away'])
    common = test_df.index[test_df['team_home'].isin(known) & test_df['team_away'].isin(known)]
    if len(common) != COMMON_TEST_FIXTURES:
        raise ValueError(f'{len(common)} common test rows; expected {COMMON_TEST_FIXTURES}.')
    assert_baseline_anchors(probability_metrics(
        rates.loc[common, ['pred_home_win', 'pred_draw', 'pred_away_win']], outcome_classes(df.loc[common])))
    print('Stage 2 rates reproduce the Step 0 anchors on the common test rows.')

    tables = load_local_tables()
    links = link_fixtures(df, tables)

    buffer = io.StringIO()
    with contextlib.redirect_stdout(_Tee(sys.stdout, buffer)):
        print('\n' + '=' * 70)
        print('LINEUP FEATURES AND GATE B')
        print('=' * 70)
        print(f'TEST_START: {TEST_START}; ESTIMATION_CUTOFF: {ESTIMATION_CUTOFF}')
        valued, status = value_starters(df, links, tables)
        fallback = fallback_value(tables['player_valuations'], ESTIMATION_CUTOFF)
        print(f'Fallback valuation F (5th pct of positive valuations before the cutoff day): {fallback:,.0f}')
        features = build_features(df, links, valued, status, fallback)

        estimation_window = (df['date'] < ESTIMATION_CUTOFF).to_numpy()
        test_window = df.index.isin(TEST_INDEX)
        report_features(features, np.ones(len(df), bool), 'All fixtures')
        report_features(features, estimation_window, 'Estimation window (date < ESTIMATION_CUTOFF)')
        report_features(features, test_window, 'Test window (TEST_INDEX)')

        keep = burn_in_keep(df, rates, prior_appearances(df), estimation_window)
        rows = estimation_rows(df, features, rates, keep, ESTIMATION_CUTOFF)
        if not rows['match_id'].isin(train_df.index).all():
            raise ValueError('An estimation row is not a training row.')
        result = fit_gate_b(rows)
        print('\nGATE B: Poisson GLM, log link, offset = log(Stage 2 rate), cluster-robust SE by match')
        print(result.summary())
        primary = gate_b_numbers(result, rows)
        print(describe_fit('Primary', primary))
        passed, reason = gate_b_verdict(primary['c_att'], primary['c_def'],
                                        primary['ci_att'], primary['ci_def'])
        print(f"GATE B: {'PASSED' if passed else 'FAILED'} ({reason})")

        print('\nDescriptive robustness (never changes the verdict):')
        for label, scale in (('F x 0.5', 0.5), ('F x 2', 2.0)):
            alt = build_features(df, links, valued, status, fallback * scale)
            alt_rows = estimation_rows(df, alt, rates, keep, ESTIMATION_CUTOFF)
            print('  ' + describe_fit(label, gate_b_numbers(fit_gate_b(alt_rows), alt_rows), primary))
        clean = rows.loc[~rows['has_fallback']].reset_index(drop=True)
        print('  ' + describe_fit('No fallback valuations', gate_b_numbers(fit_gate_b(clean), clean), primary))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(SUMMARY_PATH, 'w', encoding='utf-8') as handle:
        handle.write(buffer.getvalue())
    with open(COEFFICIENTS_PATH, 'w', encoding='utf-8') as handle:
        json.dump(dict(verdict='PASSED' if passed else 'FAILED', reason=reason, **primary,
                       fallback=fallback, test_start=str(TEST_START),
                       estimation_cutoff=str(ESTIMATION_CUTOFF)), handle, indent=2)
    print(f'Gate B summary written to {os.path.relpath(SUMMARY_PATH, PROJECT_DIR)}')
    if not passed:
        print('Gate B failed: adjustments file not built.')
        return

    save_adjustments(df, features, TEST_INDEX, TEST_START, ESTIMATION_CUTOFF,
                     primary['c_att'], primary['c_def'], (ADJUSTMENTS_PATH, PLACEBO_PATH))


def attack_only_main():
    """The one approved post-hoc specification (DECISIONS.md, 2026-10-19): frozen Gate B
    c_att, every defence delta 0. Gate B stays FAILED; nothing here is re-estimated."""
    c_att = frozen_attack_coefficient()
    df = ingest_and_clean_fixtures([], refresh=False)
    train_df, test_df = chronological_split(df)
    TEST_INDEX = test_df.index
    TEST_START = test_df['date'].min()
    ESTIMATION_CUTOFF = estimation_cutoff(TEST_START)
    if len(df) != TOTAL_FIXTURES or len(TEST_INDEX) != TEST_FIXTURES:
        raise ValueError(f'Unexpected frame sizes: {len(df)} fixtures, {len(TEST_INDEX)} test rows.')

    tables = load_local_tables()
    links = link_fixtures(df, tables)
    print('\n' + '=' * 70)
    print(f'LINEUP ADJUSTMENTS: {EXPLORATORY_LABEL}')
    print('=' * 70)
    print(f'{EXPLORATORY_LABEL}: frozen c_att={c_att:.5f} from the Gate B primary fit; '
          f'c_def=0 (all defence deltas are 0). Gate B verdict stays FAILED.')
    print(f'{EXPLORATORY_LABEL}: TEST_START {TEST_START}; ESTIMATION_CUTOFF {ESTIMATION_CUTOFF}')
    valued, status = value_starters(df, links, tables)
    fallback = fallback_value(tables['player_valuations'], ESTIMATION_CUTOFF)
    features = build_features(df, links, valued, status, fallback)
    report_features(features, df.index.isin(TEST_INDEX), f'{EXPLORATORY_LABEL} Test window (TEST_INDEX)')
    save_adjustments(df, features, TEST_INDEX, TEST_START, ESTIMATION_CUTOFF, c_att, 0.0,
                     (ATTACK_ONLY_PATH, ATTACK_ONLY_PLACEBO_PATH), EXPLORATORY_LABEL)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--exploratory-attack-only', action='store_true',
                        help=f'{EXPLORATORY_LABEL}: write the attack-only adjustments file')
    if parser.parse_args().exploratory_attack_only:
        attack_only_main()
    else:
        main()
