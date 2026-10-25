"""Selection harness for the Stage 2 experiments. Scores DEV and VAL rows only, never BURN-IN or TEST."""
import numpy as np
import pandas as pd

from metrics import outcome_classes, probability_metrics

DEV_START = pd.Timestamp('2020-07-01')
VAL_START = pd.Timestamp('2023-07-01')
CI_LEVEL = 0.99
N_RESAMPLES = 2000
BOOTSTRAP_SEED = 20261025
PROB_COLUMNS = ['pred_home_win', 'pred_draw', 'pred_away_win']
MARKET_COLUMNS = ['avg_ch', 'avg_cd', 'avg_ca']
LABEL = 'selection-period, retrospective, not out-of-sample'


def split_index(df, test_index):
    """BURN-IN / DEV / VAL row ids. TEST rows are excluded by identity, never by date."""
    non_test = df.loc[~df.index.isin(test_index)]
    dates = non_test['date']
    splits = dict(burn_in=non_test.index[dates < DEV_START],
                  dev=non_test.index[(dates >= DEV_START) & (dates < VAL_START)],
                  val=non_test.index[dates >= VAL_START])
    for name, ids in splits.items():
        if ids.isin(test_index).any():
            raise AssertionError(f'{name} contains TEST_INDEX rows.')
    if sum(len(ids) for ids in splits.values()) != len(non_test):
        raise AssertionError('Splits do not partition the non-TEST rows.')
    return splits


def assert_no_test(frame, test_index):
    if frame.index.isin(test_index).any():
        raise AssertionError('A TEST_INDEX row reached a scored frame.')


def row_scores(probs, actual_class):
    """Per-row log-loss, RPS and Brier, on the same scales as metrics.probability_metrics."""
    probs = np.asarray(probs, float)
    actual = np.eye(3)[actual_class]
    positions = np.arange(len(actual_class))
    return dict(
        LogLoss=-np.log(np.clip(probs[positions, actual_class], 1e-15, 1.0)),
        RPS=np.mean((np.cumsum(probs, axis=1)[:, :2] - np.cumsum(actual, axis=1)[:, :2]) ** 2, axis=1),
        Brier=np.mean((probs - actual) ** 2, axis=1))


def scored(frame, test_index, probs=None):
    """(probabilities, actual classes) for a frame, after the TEST guard."""
    assert_no_test(frame, test_index)
    probs = frame[PROB_COLUMNS].to_numpy(float) if probs is None else np.asarray(probs, float)
    return probs, outcome_classes(frame)


def summary(frame, test_index, probs=None):
    probs, actual = scored(frame, test_index, probs)
    return dict(n=len(frame), **probability_metrics(probs, actual))


def week_block_ci(delta, dates, level=CI_LEVEL, n_resamples=N_RESAMPLES, seed=BOOTSTRAP_SEED):
    """metrics.paired_week_block_ci with a chosen level and seed, plus a one-sided p-value.

    p = (1 + #{resampled mean delta >= 0}) / (B + 1): evidence that the candidate is not better.
    """
    week_ids = pd.Series(dates).dt.to_period('W').astype(str).to_numpy()
    weekly = pd.DataFrame(dict(week=week_ids, delta=delta)).groupby('week').delta.agg(['sum', 'count'])
    rng = np.random.default_rng(seed)
    resamples = rng.integers(len(weekly), size=(n_resamples, len(weekly)))
    bootstrap_delta = (weekly['sum'].to_numpy()[resamples].sum(axis=1)
                       / weekly['count'].to_numpy()[resamples].sum(axis=1))
    low, high = np.quantile(bootstrap_delta, [round((1 - level) / 2, 12), round((1 + level) / 2, 12)])
    p_value = (1 + int((bootstrap_delta >= 0).sum())) / (n_resamples + 1)
    return float(low), float(high), float(p_value)


def accept(dev_incumbent, dev_candidate, val_incumbent, val_candidate, ci_high):
    """Locked rule: DEV and VAL log-loss both improve and the 99% CI upper bound is below 0."""
    checks = {'(i) DEV log-loss improves': dev_candidate < dev_incumbent,
              '(ii) VAL log-loss improves': val_candidate < val_incumbent,
              '(iii) 99% CI upper bound < 0': ci_high < 0}
    return all(checks.values()), checks


def holm(p_values):
    p_values = np.asarray(p_values, float)
    order = np.argsort(p_values, kind='stable')
    adjusted = np.empty_like(p_values)
    running = 0.0
    for rank, position in enumerate(order):
        running = max(running, (len(p_values) - rank) * p_values[position])
        adjusted[position] = min(1.0, running)
    return adjusted


def climatology(train_rows, test_index):
    assert_no_test(train_rows, test_index)
    return np.bincount(outcome_classes(train_rows), minlength=3) / len(train_rows)


def murphy(probs, actual_class, bins=10):
    """Brier decomposition per class (10 equal-width bins), scaled like metrics' Brier (/3)."""
    records = []
    for cls, name in enumerate(('Home', 'Draw', 'Away')):
        p = np.asarray(probs)[:, cls]
        y = (np.asarray(actual_class) == cls).astype(float)
        groups = np.minimum((p * bins).astype(int), bins - 1)
        base_rate = y.mean()
        reliability = resolution = 0.0
        for group in np.unique(groups):
            mask = groups == group
            weight = mask.mean()
            reliability += weight * (p[mask].mean() - y[mask].mean()) ** 2
            resolution += weight * (y[mask].mean() - base_rate) ** 2
        brier = np.mean((p - y) ** 2)
        uncertainty = base_rate * (1 - base_rate)
        records.append(dict(outcome=name, reliability=reliability / 3, resolution=resolution / 3,
                            uncertainty=uncertainty / 3, within_bin=(brier - reliability + resolution
                                                                    - uncertainty) / 3,
                            brier=brier / 3))
    table = pd.DataFrame(records)
    total = table.drop(columns='outcome').sum()
    return pd.concat([table, pd.DataFrame([dict(outcome='Total', **total)])], ignore_index=True)


def favourite_table(probs, actual_class):
    """Favourite = the side (home or away) with the higher forecast win probability."""
    probs = np.asarray(probs, float)
    home_favourite = probs[:, 0] >= probs[:, 2]
    favourite_p = np.where(home_favourite, probs[:, 0], probs[:, 2])
    underdog_p = np.where(home_favourite, probs[:, 2], probs[:, 0])
    favourite_won = np.where(home_favourite, actual_class == 0, actual_class == 2)
    underdog_won = np.where(home_favourite, actual_class == 2, actual_class == 0)
    draw = actual_class == 1
    bands = pd.cut(favourite_p, [0, 0.45, 0.60, 1.0], labels=['fav p < 0.45', '0.45-0.60', 'fav p >= 0.60'],
                   include_lowest=True)
    records = []
    for band in ['all'] + list(bands.categories):
        mask = np.ones(len(probs), bool) if band == 'all' else np.asarray(bands == band)
        if mask.any():
            records.append({'band': band, 'n': int(mask.sum()),
                            'fav forecast': favourite_p[mask].mean(), 'fav observed': favourite_won[mask].mean(),
                            'draw forecast': probs[mask, 1].mean(), 'draw observed': draw[mask].mean(),
                            'dog forecast': underdog_p[mask].mean(), 'dog observed': underdog_won[mask].mean()})
    return pd.DataFrame(records)


def market_probs(rows):
    """Normalised closing-average implied probabilities (evaluation only), as in main.py."""
    odds = rows[MARKET_COLUMNS].apply(pd.to_numeric, errors='coerce').to_numpy()
    mask = np.isfinite(odds).all(axis=1) & (odds > 1.0).all(axis=1)
    implied = 1.0 / np.where(mask[:, None], odds, np.nan)
    return implied / implied.sum(axis=1, keepdims=True), mask


def skill_table(rows, test_index, model_probs, climate):
    """RPS skill vs climatology, and closing-market comparisons on rows with closing odds.

    model_probs: {'Baseline': array, 'Candidate': array}, aligned to rows.
    """
    _, actual = scored(rows, test_index, next(iter(model_probs.values())))
    market, mask = market_probs(rows)
    climate_probs = np.tile(climate, (len(rows), 1))
    rps = {name: row_scores(probs, actual)['RPS'] for name, probs in model_probs.items()}
    rps_climate = row_scores(climate_probs, actual)['RPS']
    rps_market = row_scores(market[mask], actual[mask])['RPS'].mean() if mask.any() else np.nan
    records = []
    for name, values in rps.items():
        on_market = values[mask].mean()
        records.append({'model': name, 'RPS': values.mean(), 'RPS skill vs clim': 1 - values.mean() / rps_climate.mean(),
                        'n market rows': int(mask.sum()), 'RPS (market rows)': on_market,
                        'RPS skill (market rows)': 1 - on_market / rps_climate[mask].mean(),
                        'market RPS': rps_market,
                        'clim-to-market share': (rps_climate[mask].mean() - on_market)
                        / (rps_climate[mask].mean() - rps_market)})
    table = pd.DataFrame(records)
    names = list(rps)
    base, candidate = rps[names[0]][mask].mean(), rps[names[-1]][mask].mean()
    gap_closed = (base - candidate) / (base - rps_market)
    return table, float(gap_closed)


def markdown_table(frame, digits=5):
    def cell(value):
        if isinstance(value, (float, np.floating)):
            return f'{value:.{digits}f}' if np.isfinite(value) else 'n/a'
        return str(value)
    columns = list(frame.columns)
    lines = ['| ' + ' | '.join(map(str, columns)) + ' |', '|' + '---|' * len(columns)]
    lines += ['| ' + ' | '.join(cell(value) for value in row) + ' |' for row in frame.itertuples(index=False)]
    return '\n'.join(lines)


def grouped_metrics(frame, test_index, probs_by_model, key):
    records = []
    for group, ids in frame.groupby(key).groups.items():
        positions = frame.index.get_indexer(ids)
        for name, probs in probs_by_model.items():
            records.append({key: group, 'model': name,
                            **summary(frame.loc[ids], test_index, np.asarray(probs)[positions])})
    return pd.DataFrame(records)


def report(frames, test_index, probs, climate, train_rows):
    """Baseline vs candidate on DEV and VAL. frames: {'DEV': rows, 'VAL': rows};
    probs: {'DEV': {'Baseline': p, 'Candidate': p}, 'VAL': {...}}."""
    assert_no_test(train_rows, test_index)
    lines = [f'All numbers below are {LABEL}. TEST rows are not scored.', '']
    for split, rows in frames.items():
        models = probs[split]
        lines += [f'## {split} ({len(rows)} matches)', '', '### Overall', '',
                  markdown_table(pd.DataFrame([{'model': name, **summary(rows, test_index, p)}
                                               for name, p in models.items()])), '']
        skills, gap_closed = skill_table(rows, test_index, models, climate)
        lines += ['### Skill and closing market', '',
                  f'Climatology = training-window outcome rates H/D/A {np.round(climate, 4).tolist()} '
                  f'({len(train_rows)} non-TEST matches; in-sample for this reference).', '',
                  markdown_table(skills), '',
                  f'Share of the baseline-to-closing-market RPS gap closed by the candidate: {gap_closed:.2%}', '']
        for key in ('season', 'competition'):
            lines += [f'### Per {key}', '', markdown_table(grouped_metrics(rows, test_index, models, key)), '']
        for name, p in models.items():
            p, actual = scored(rows, test_index, p)
            lines += [f'### Brier Murphy decomposition: {name}', '', markdown_table(murphy(p, actual), 6), '',
                      f'### Favourite vs underdog: {name}', '', markdown_table(favourite_table(p, actual), 4), '']
    return '\n'.join(lines)


# Football-data 1X2 triples (home, draw, away). A C after the bookmaker code marks closing odds.
# Note: bfd* is Betfred (bfdh/bfdd/bfda), unlike bfh/bfd/bfa (Betfair); cl* is Coolbet.
PRE_CLOSING_TRIPLES = [('b365_h', 'b365_d', 'b365_a'), ('bwh', 'bwd', 'bwa'), ('iwh', 'iwd', 'iwa'),
                       ('psh', 'psd', 'psa'), ('whh', 'whd', 'wha'), ('vch', 'vcd', 'vca'),
                       ('max_h', 'max_d', 'max_a'), ('avg_h', 'avg_d', 'avg_a'), ('bfh', 'bfd', 'bfa'),
                       ('1_xbh', '1_xbd', '1_xba'), ('bfeh', 'bfed', 'bfea'), ('bfdh', 'bfdd', 'bfda'),
                       ('bmgmh', 'bmgmd', 'bmgma'), ('bvh', 'bvd', 'bva'), ('clh', 'cld', 'cla'),
                       ('lbh', 'lbd', 'lba')]
CLOSING_TRIPLES = [('b365_ch', 'b365_cd', 'b365_ca'), ('bwch', 'bwcd', 'bwca'), ('iwch', 'iwcd', 'iwca'),
                   ('psch', 'pscd', 'psca'), ('whch', 'whcd', 'whca'), ('vcch', 'vccd', 'vcca'),
                   ('max_ch', 'max_cd', 'max_ca'), ('avg_ch', 'avg_cd', 'avg_ca'), ('bfch', 'bfcd', 'bfca'),
                   ('1_xbch', '1_xbcd', '1_xbca'), ('bfech', 'bfecd', 'bfeca'), ('bfdch', 'bfdcd', 'bfdca'),
                   ('bmgmch', 'bmgmcd', 'bmgmca'), ('bvch', 'bvcd', 'bvca'), ('clch', 'clcd', 'clca'),
                   ('lbch', 'lbcd', 'lbca')]
PRE_CLOSING_OTHER = ['b365>2.5', 'b365<2.5', 'p>2.5', 'p<2.5', 'max>2.5', 'max<2.5', 'avg>2.5', 'avg<2.5',
                     'bfe>2.5', 'bfe<2.5', 'a_hh', 'b365_ahh', 'b365_aha', 'pahh', 'paha', 'max_ahh',
                     'max_aha', 'avg_ahh', 'avg_aha', 'bfeahh', 'bfeaha']
CLOSING_OTHER = ['b365_c>2.5', 'b365_c<2.5', 'pc>2.5', 'pc<2.5', 'max_c>2.5', 'max_c<2.5', 'avg_c>2.5',
                 'avg_c<2.5', 'bfec>2.5', 'bfec<2.5', 'ah_ch', 'b365_cahh', 'b365_caha', 'pcahh', 'pcaha',
                 'max_cahh', 'max_caha', 'avg_cahh', 'avg_caha', 'bfecahh', 'bfecaha']
NON_ODDS_COLUMNS = ['date', 'datetime', 'season', 'competition', 'div', 'time', 'team_home', 'team_away',
                    'fthg', 'ftag', 'ftr', 'hthg', 'htag', 'htr', 'referee', 'hs', 'as', 'hst', 'ast', 'hf',
                    'af', 'hc', 'ac', 'hy', 'ay', 'hr', 'ar', 'goals_home', 'goals_away', 'ï»¿_div']


def classify_odds_columns(columns):
    """Every non-match column must be a known odds column; unknown columns raise."""
    known = {}
    for triple in PRE_CLOSING_TRIPLES:
        known.update({column: ('1X2', 'non-closing') for column in triple})
    for triple in CLOSING_TRIPLES:
        known.update({column: ('1X2', 'closing') for column in triple})
    known.update({column: ('O/U 2.5 or Asian handicap', 'non-closing') for column in PRE_CLOSING_OTHER})
    known.update({column: ('O/U 2.5 or Asian handicap', 'closing') for column in CLOSING_OTHER})
    unknown = [column for column in columns if column not in known and column not in NON_ODDS_COLUMNS]
    if unknown:
        raise ValueError(f'Unclassified columns: {unknown}')
    return pd.DataFrame([dict(column=column, market=known[column][0], timing=known[column][1])
                         for column in columns if column in known])


def triple_missing(rows, triple):
    """Share of rows without a valid triple (missing, non-numeric, or odds <= 1), and non-numeric count."""
    raw = rows[list(triple)]
    numeric = raw.apply(pd.to_numeric, errors='coerce')
    text = int((numeric.isna() & raw.notna()).any(axis=1).sum())
    valid = (numeric > 1.0).all(axis=1)
    return 1.0 - float(valid.mean()), text


def odds_audit(df, test_index):
    """Coverage of every odds-like column on non-TEST rows (read-only; no outcomes, no forecasts)."""
    rows = df.loc[~df.index.isin(test_index)]
    columns = classify_odds_columns(list(df.columns))
    overall, by_group = [], {}
    for timing, triples in (('non-closing', PRE_CLOSING_TRIPLES), ('closing', CLOSING_TRIPLES)):
        for triple in triples:
            name = '/'.join(triple)
            share, text = triple_missing(rows, triple)
            per_group = {f'{league} {season}': triple_missing(group, triple)[0]
                         for (league, season), group in rows.groupby(['competition', 'season'])}
            by_group[name] = per_group
            overall.append(dict(triple=name, timing=timing, missing_share=share,
                                worst_league_season=max(per_group.values()),
                                league_seasons_complete=sum(value == 0 for value in per_group.values()),
                                non_numeric_rows=text))
    return columns, pd.DataFrame(overall), pd.DataFrame(by_group)
