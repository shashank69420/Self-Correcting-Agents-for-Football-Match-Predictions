"""Fan-facing data layer from the frozen P2 goals-only model (fan/NOTES.md). Descriptive only.

python -X utf8 fan_features.py --markets   goal markets and their calibration (results/fan/markets_calibration.*)
python -X utf8 fan_features.py --ratings   team ratings with the filter's own uncertainty (results/fan/ratings.*)
python -X utf8 fan_features.py --outputs   model constants and sample forecasts for the browser parity test
python -X utf8 fan_features.py             all three

The filter runs once over the concatenation of H (2019-2026, the cache) and the committed 2026-27 snapshot, as
live2627 does; a row's forecast uses only earlier rows. No model code or frozen parameter is changed, nothing is
tuned, and no metric is computed on a TEST_INDEX row.
"""
import argparse
import hashlib
import inspect
import json
import os
import subprocess
from unittest import mock

import numpy as np
import pandas as pd
from scipy.stats import poisson, spearmanr

import exp_harness as harness
import exp_model
import live2627
import p2_model
from run_experiments import FILTER_COLUMNS

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS = 'results/fan'
SNAPSHOT_DATE = '20261026'
SNAPSHOT_ISO = f'{SNAPSHOT_DATE[:4]}-{SNAPSHOT_DATE[4:6]}-{SNAPSHOT_DATE[6:]}'
MARKET_GOALS = 30
MODEL_GOALS = inspect.signature(exp_model.dixon_coles_probs).parameters['max_goals'].default
MIN_MASS = 1 - 1e-7
TOP_K = 5
OVER_LINE = 2.5
BINS = 10
Z95 = 1.959963984540054
DIAGNOSTIC_FLAG = 0.01
SAMPLE_SIZE = 5
WORDING = ('Parameters were fixed before 2026-27 data was fetched. Forecasts were recomputed after the matches were '
           'played and are not timestamped before kickoff.')
DESCRIPTIVE = 'DESCRIPTIVE: recomputed forecasts, not timestamped before kickoff; no test, no claim'
CENTRING_TOLERANCE = 1e-9
BAR_LABEL = 'model uncertainty, not measured accuracy'
DEFENCE_BAR_NOTE = ("Defence bars do not narrow with more matches. This most likely reflects how the model's variance "
                    'behaves. A simulation reproduced the signs but could not separate this from team selection, so '
                    'treat it as unconfirmed (see ratings_check.md).')
SIM_SEED = 20261028
SIM_DESIGN = dict(leagues=8, teams=20, seasons=7, relegated=3)
SIM_START = '2020-08-01'


def git(*args):
    return subprocess.run(['git', *args], cwd=PROJECT_DIR, capture_output=True, text=True).stdout.strip()


def code_provenance():
    """HEAD, the sha256 of this file, and whether this file differs from HEAD."""
    with open(os.path.join(PROJECT_DIR, 'fan_features.py'), 'rb') as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    return dict(code_commit=git('rev-parse', 'HEAD'), fan_features_sha256=digest,
                fan_features_dirty=bool(git('status', '--porcelain', '--', 'fan_features.py')))


# ---------------------------------------------------------------- grid and markets

def score_grid(lambda_home, mu_away, rho, max_goals=MARKET_GOALS, min_mass=MIN_MASS):
    """Normalised score grid (rows home goals, columns away goals), the lines of exp_model.dixon_coles_probs with a
    configurable size. Raises if the Poisson product mass before the rho factors is below min_mass."""
    if not np.isfinite([lambda_home, mu_away]).all():
        raise FloatingPointError("Non-finite pre-match goal rate.")
    goals = np.arange(max_goals + 1)
    grid = np.outer(poisson.pmf(goals, lambda_home), poisson.pmf(goals, mu_away))
    mass = grid.sum()
    if not mass >= min_mass:
        raise ValueError(f'Score grid mass {mass!r} at max_goals {max_goals} is below {min_mass!r} '
                         f'(lambda {lambda_home}, mu {mu_away}).')
    if rho != 0.0:
        grid[0, 0] *= max(1.0 - lambda_home * mu_away * rho, 0.0)
        grid[0, 1] *= max(1.0 + lambda_home * rho, 0.0)
        grid[1, 0] *= max(1.0 + mu_away * rho, 0.0)
        grid[1, 1] *= max(1.0 - rho, 0.0)
    grid_mass = grid.sum()
    if not np.isfinite(grid_mass) or grid_mass <= 0:
        raise FloatingPointError("The specified score grid has no finite positive mass.")
    return grid / grid_mass


def outcome_probs(grid):
    return float(np.tril(grid, k=-1).sum()), float(np.trace(grid)), float(np.triu(grid, k=1).sum())


def expected_goals(grid):
    goals = np.arange(grid.shape[0])
    return float(goals @ grid.sum(axis=1)), float(goals @ grid.sum(axis=0))


def top_scorelines(grid, k=TOP_K):
    """[(home goals, away goals, probability)], probability descending, then home goals, then away goals."""
    home, away = np.unravel_index(np.arange(grid.size), grid.shape)
    order = np.lexsort((away, home, -grid.ravel()))[:k]
    return [(int(home[i]), int(away[i]), float(grid.ravel()[i])) for i in order]


def p_over(grid, line=OVER_LINE):
    """P(total goals > line); with line 2.5, P(total >= 3)."""
    total = np.add.outer(np.arange(grid.shape[0]), np.arange(grid.shape[1]))
    return float(grid[total > line].sum())


def p_btts(grid):
    return float(grid[1:, 1:].sum())


def markets(grid):
    home, draw, away = outcome_probs(grid)
    xg_home, xg_away = expected_goals(grid)
    return dict(home=home, draw=draw, away=away, xg_home=xg_home, xg_away=xg_away,
                top_scorelines=[dict(home_goals=h, away_goals=a, p=p) for h, a, p in top_scorelines(grid)],
                over_2_5=p_over(grid), under_2_5=1.0 - p_over(grid), btts=p_btts(grid), btts_no=1.0 - p_btts(grid))


# ---------------------------------------------------------------- data and model

def load_frames(date=SNAPSHOT_DATE):
    """H, L and their concatenation with live2627's own helpers; the live test set and the flagged names."""
    if live2627.snapshot_failures(date):
        raise RuntimeError(f'Snapshot {date} fails its checks: {live2627.snapshot_failures(date)}')
    history = live2627.load_history()
    live = live2627.live_frame(live2627.read_json(live2627.snapshot_name(date))['rows'])
    names, _, stops = live2627.data_checks(history, live)
    if stops:
        raise SystemExit('STOP: ' + '; '.join(stops))
    both, cast = live2627.concatenate(history, live)
    forward_keys, _ = live2627.forward_state()
    flagged = names.loc[names['flagged']]
    scored, logged, named = live2627.select_scored(both, history, forward_keys, sorted(flagged['team']))
    return dict(history=history, live=live, both=both, cast=cast, names=names, flagged=flagged, scored=scored,
                excluded_forward=len(logged), excluded_flagged=len(named))


def load_model():
    """(P2 goals-only overrides, exp_model parameter set with defaults, home_adv, candidate self-hash)."""
    _, p2_params, p2_sha = live2627.load_models()
    model, _ = p2_model.split_params(p2_params)
    return p2_params, model, live2627.HOME_ADV, p2_sha


def final_states(frame, params, home_adv):
    """p2_model.run_filter's forecasts and the team states after its last update, recorded by wrapping
    p2_model.update_step (the forward_logger.snapshot_states approach); no filter maths is copied."""
    original, seen = p2_model.update_step, []

    def recording_update(home_state, away_state, *args):
        seen.append((home_state, away_state))
        return original(home_state, away_state, *args)

    with mock.patch.object(p2_model, 'update_step', recording_update):
        forecasts = p2_model.run_filter(frame, params, home_adv)
    if len(seen) != len(forecasts):
        raise RuntimeError('run_filter did not update once per row')
    states = {}
    for (home_state, away_state), home, away in zip(seen, forecasts['team_home'], forecasts['team_away']):
        for team, state in ((home, home_state), (away, away_state)):
            if states.setdefault(team, state) is not state:
                raise RuntimeError(f'run_filter used more than one state object for {team}')
    return states, forecasts


def run_model(both, params, home_adv):
    """One wrapped run over the concatenation (live2627's M2 input), checked equal to an unwrapped run."""
    frame = both[FILTER_COLUMNS + list(p2_model.SOT_COLUMNS)]
    states, forecasts = final_states(frame, params, home_adv)
    plain = p2_model.run_filter(frame, params, home_adv)
    if not forecasts.equals(plain):
        raise RuntimeError('The wrapped filter run differs from the unwrapped run.')
    return states, forecasts


# ---------------------------------------------------------------- per-row markets

def row_markets(forecasts, rho):
    """Per row: markets from the corrected 30-goal grid, outcomes, and the 1X2 difference to the model's own
    max_goals 10 forecast (the pred_* columns of run_filter)."""
    records = []
    for row in forecasts.itertuples():
        grid = score_grid(row.lambda_home, row.mu_away, rho)
        home, draw, away = outcome_probs(grid)
        top = top_scorelines(grid, 3)
        actual = (int(row.goals_home), int(row.goals_away))
        records.append(dict(
            p_over=p_over(grid), p_btts=p_btts(grid),
            y_over=float(sum(actual) > OVER_LINE), y_btts=float(min(actual) >= 1),
            top1_p=top[0][2], top1_hit=float(actual == top[0][:2]),
            top3_p=sum(p for _, _, p in top), top3_hit=float(actual in [t[:2] for t in top]),
            diff_1x2=float(np.abs(np.array([home, draw, away]) - np.array(
                [row.pred_home_win, row.pred_draw, row.pred_away_win])).max())))
    return pd.DataFrame(records, index=forecasts.index)


def climatology_rates(both, scored_index):
    """Over 2.5 and BTTS base rates over H rows dated before 2020-07-01 (none scored, none TEST)."""
    rows = both.loc[(both['frame'] == 'H') & (both['date'] < harness.DEV_START)]
    if rows['is_test'].any() or rows.index.isin(scored_index).any():
        raise AssertionError('The climatology rows contain a TEST or scored row.')
    total = rows['goals_home'] + rows['goals_away']
    return dict(over_2_5=float((total > OVER_LINE).mean()),
                btts=float(((rows['goals_home'] >= 1) & (rows['goals_away'] >= 1)).mean()),
                n=len(rows), last_date=str(rows['date'].max()))


def val_index(both):
    """VAL: exp_harness.split_index's val rows of H (non-TEST H rows dated from 2023-07-01)."""
    history = both.loc[both['frame'] == 'H']
    return harness.split_index(history, history.index[history['is_test']])['val']


# ---------------------------------------------------------------- calibration

def hw_rate(p, n):
    return float(Z95 * np.sqrt(p * (1 - p) / n)) if n else float('nan')


def hw_mean(values):
    values = np.asarray(values, float)
    return float(Z95 * values.std(ddof=1) / np.sqrt(len(values))) if len(values) > 1 else float('nan')


def binary_losses(p, y):
    p, y = np.asarray(p, float), np.asarray(y, float)
    return (p - y) ** 2, -(y * np.log(p) + (1 - y) * np.log(1 - p))


def reliability(p, y, bins=BINS):
    """Equal-width bins on [0, 1]: count, mean predicted, observed rate and its 95% half-width."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    which = np.minimum((p * bins).astype(int), bins - 1)
    table = []
    for b in range(bins):
        mask = which == b
        n = int(mask.sum())
        observed = float(y[mask].mean()) if n else float('nan')
        table.append(dict(bin=f'[{b / bins:.1f}, {(b + 1) / bins:.1f}{"]" if b == bins - 1 else ")"}', n=n,
                          mean_predicted=float(p[mask].mean()) if n else float('nan'),
                          observed=observed, observed_hw95=hw_rate(observed, n) if n else float('nan')))
    return table


def binary_block(p, y, base_rate):
    """Brier and log-loss of the model and of the constant climatology rate, skill, and calibration in the large."""
    n = len(p)
    brier, logloss = binary_losses(p, y)
    brier_c, logloss_c = binary_losses(np.full(n, base_rate), y)
    observed = float(np.mean(y))
    return dict(n=n, brier=float(brier.mean()), brier_climatology=float(brier_c.mean()),
                brier_skill=float(1 - brier.mean() / brier_c.mean()),
                brier_diff=float((brier - brier_c).mean()), brier_diff_hw95=hw_mean(brier - brier_c),
                log_loss=float(logloss.mean()), log_loss_climatology=float(logloss_c.mean()),
                log_loss_diff=float((logloss - logloss_c).mean()), log_loss_diff_hw95=hw_mean(logloss - logloss_c),
                climatology_rate=base_rate, mean_predicted=float(np.mean(p)), mean_predicted_hw95=hw_mean(p),
                observed=observed, observed_hw95=hw_rate(observed, n), reliability=reliability(p, y))


def scoreline_block(rows):
    n = len(rows)
    out = dict(n=n)
    for k in ('top1', 'top3'):
        hit = float(rows[f'{k}_hit'].mean())
        out[k] = dict(hit_rate=hit, hit_rate_hw95=hw_rate(hit, n), mean_predicted=float(rows[f'{k}_p'].mean()),
                      mean_predicted_hw95=hw_mean(rows[f'{k}_p']))
    return out


def calibration(rows, climate):
    return dict(over_2_5=binary_block(rows['p_over'], rows['y_over'], climate['over_2_5']),
                btts=binary_block(rows['p_btts'], rows['y_btts'], climate['btts']),
                scorelines=scoreline_block(rows))


def grid_diagnostic(rows, frame, sets):
    """Max |1X2(30-goal grid) - 1X2(model, max_goals 10)| per set and the rows above DIAGNOSTIC_FLAG."""
    out = {}
    for name, index in sets.items():
        diff = rows.loc[index, 'diff_1x2']
        above = frame.loc[diff.index[diff > DIAGNOSTIC_FLAG]]
        out[name] = dict(n=len(diff), max_abs_diff=float(diff.max()), rows_above_0_01=[
            dict(date=str(r.date), league=r.competition, home=r.team_home, away=r.team_away,
                 lambda_home=float(r.lambda_home), mu_away=float(r.mu_away),
                 diff=float(rows.loc[i, 'diff_1x2'])) for i, r in above.iterrows()])
    return out


# ---------------------------------------------------------------- writing

def write_json(name, payload, root=None):
    path = os.path.join(root or PROJECT_DIR, RESULTS, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write('\n')


def write_text(name, text, root=None):
    path = os.path.join(root or PROJECT_DIR, RESULTS, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)


def fmt(value, digits=4):
    if isinstance(value, float):
        return 'n/a' if np.isnan(value) else f'{value:.{digits}f}'
    return str(value)


def md_table(records, columns, digits=4):
    lines = ['| ' + ' | '.join(columns) + ' |', '|' + '---|' * len(columns)]
    lines += ['| ' + ' | '.join(fmt(r[c], digits) for c in columns) + ' |' for r in records]
    return '\n'.join(lines)


def header(title, provenance):
    return [f'# {title}', '', f'**{DESCRIPTIVE}.**', '', WORDING, '',
            f'Model: frozen P2 goals-only (`results/p2/candidate_p2.json`, sha256 {provenance["params_sha256"]}); '
            f'code commit {provenance["code_commit"]} (fan_features.py sha256 {provenance["fan_features_sha256"][:16]}..., '
            f'differs from that commit: {provenance["fan_features_dirty"]}).', '']


def markets_text(payload):
    """The human-readable report: no table values. Every number is in markets_calibration.json; the comparisons
    below are stated in words from that payload (a gap against its own interval; descriptive, not a test)."""
    lines = header('Goal markets: calibration', payload['provenance'])
    lines += ['Forecasts: one run of the filter over the concatenated history and the 2026-27 snapshot; a row\'s forecast '
              'uses only earlier rows. Markets come from the rho-corrected market score grid. Nothing was tuned or '
              'recalibrated. No TEST_INDEX row is scored. Half-widths are normal approximations at the usual two-sided '
              'level.', '',
              'The over market is over 2.5 goals in total; BTTS is both teams to score. The climatology baseline is the '
              'base rate over history rows dated before the DEV start, so it never sees a scored row.', '',
              'Numbers are not repeated here. They are in `markets_calibration.json`: `calibration.live` and '
              '`calibration.val` (Brier and log-loss against climatology, Brier skill, mean predicted against observed '
              'rate, a reliability table with counts, scoreline hit rates), `climatology`, and `grid_diagnostic`.', '']
    for set_name, title in (('live', 'Live 2026-27 test set'), ('val', 'VAL (history rows from the VAL start date '
                                                                       'onward, excluding TEST_INDEX)')):
        block = payload['calibration'][set_name]
        lines += [f'## {title}', '']
        for market, label in (('over_2_5', 'Over 2.5'), ('btts', 'BTTS')):
            b = block[market]
            beats = b['brier_diff'] < 0 and abs(b['brier_diff']) > b['brier_diff_hw95']
            gap = b['observed'] - b['mean_predicted']
            lines.append(f'- {label}: the Brier score is {"better than" if b["brier_diff"] < 0 else "no better than"} '
                         f'climatology and the difference is {"outside" if beats else "inside"} its interval. The mean '
                         f'predicted rate is {"below" if gap > 0 else "above"} the observed rate, and the gap is '
                         f'{"outside" if abs(gap) > b["observed_hw95"] else "inside"} the interval of the observed rate.')
        s = block['scorelines']
        for key, label in (('top1', 'most likely scoreline'), ('top3', 'three most likely scorelines')):
            gap = s[key]['hit_rate'] - s[key]['mean_predicted']
            lines.append(f'- The hit rate of the {label} is {"above" if gap > 0 else "below"} its mean predicted '
                         f'probability, and the gap is {"outside" if abs(gap) > s[key]["hit_rate_hw95"] else "inside"} '
                         'the interval of the hit rate.')
        lines.append('')
    lines += ['## Grid diagnostic', '',
              'The market grid and the model\'s own smaller grid give the same 1X2 to within a small difference. The largest '
              'difference per set is in `grid_diagnostic`. This is a description, not a failure.', '']
    for set_name, d in payload['grid_diagnostic'].items():
        rows = d['rows_above_0_01']
        lines.append(f'- {set_name}: ' + ('no row exceeds the flag threshold.' if not rows
                                          else 'rows above the flag threshold are listed in the JSON.'))
    return '\n'.join(lines) + '\n'


def without_provenance(payload):
    return json.dumps({k: v for k, v in payload.items() if k != 'provenance'}, sort_keys=True)


def keep_committed(stem, payload, text_of, root=None):
    """Write stem.json and stem.md if they do not exist. If the JSON exists, the recomputed payload must equal it apart
    from the provenance block, and the JSON is left untouched (a committed result never changes); only the report text,
    which is derived from that committed JSON, is rewritten."""
    path = os.path.join(root or PROJECT_DIR, RESULTS, f'{stem}.json')
    if not os.path.isfile(path):
        write_json(f'{stem}.json', payload, root)
        write_text(f'{stem}.md', text_of(payload), root)
        return payload
    with open(path, encoding='utf-8') as handle:
        committed = json.load(handle)
    if without_provenance(committed) != without_provenance(payload):
        raise RuntimeError(f'{stem}.json is committed and the recomputed payload differs from it; nothing written.')
    write_text(f'{stem}.md', text_of(committed), root)  # the report is derived from the committed JSON, which stays
    return committed


def run_markets(frames, model, forecasts, provenance):
    rho = model['rho']
    both, scored = frames['both'], frames['scored']
    sets = dict(live=scored.index, val=val_index(both))
    if both.loc[sets['val'], 'is_test'].any() or both.loc[sets['live'], 'is_test'].any():
        raise AssertionError('A scored set contains a TEST_INDEX row.')
    index = sets['live'].append(sets['val'])
    rows = row_markets(forecasts.loc[index], rho)
    climate = climatology_rates(both, index)
    frame = both.join(forecasts[['lambda_home', 'mu_away']])
    payload = dict(label=DESCRIPTIVE, wording=WORDING, provenance=provenance,
                   counts=dict(concatenated=len(both), live=len(sets['live']), val=len(sets['val']),
                               excluded_forward_log=frames['excluded_forward'],
                               excluded_flagged=frames['excluded_flagged']),
                   grid=dict(market_max_goals=MARKET_GOALS, model_max_goals=MODEL_GOALS, min_mass=MIN_MASS, rho=rho),
                   climatology=climate,
                   calibration={name: calibration(rows.loc[idx], climate) for name, idx in sets.items()},
                   grid_diagnostic=grid_diagnostic(rows, frame, sets))
    return keep_committed('markets_calibration', payload, markets_text)


# ---------------------------------------------------------------- ratings

def appearances(frame):
    return pd.concat([frame['team_home'], frame['team_away']]).value_counts()


def flagged_records(names):
    """Teams flagged by live2627.name_audit, with the reason; they are listed and excluded, never merged."""
    records = []
    for row in names.loc[names['flagged']].itertuples():
        reasons = ([f'club_id alias of {row.alias_of} (live2627.CLUB_ID_ALIASES, results/live2627/data_audit.md)']
                   if row.alias_of else []) + (['WRatio 88 or more'] if row.flagged_wratio else [])
        records.append(dict(league=row.league, team=row.team, reason='; '.join(reasons),
                            alias_of=live2627.CLUB_ID_ALIASES.get(row.team, {}).get('h_name', '')))
    return records


def rank(values, best_high):
    """1 is best; ties share the lower rank (method 'min')."""
    return pd.Series(values).rank(ascending=not best_high, method='min').astype(int).to_list()


def league_ratings(states, history, live, flagged):
    """Per league: active 2026-27 teams (at least one completed L match) minus flagged teams, with attack and defence
    factors exp(mean - centre), centre the mean of the posterior means over those teams, and bars exp(centred mean
    plus or minus one sd). Every bar carries BAR_LABEL; every league carries DEFENCE_BAR_NOTE."""
    excluded = {(f['league'], f['team']) for f in flagged}
    h_count, l_count = appearances(history), appearances(live)
    leagues = []
    for league in pd.unique(live['competition']):
        rows = live.loc[live['competition'] == league]
        teams = sorted(t for t in set(rows['team_home']) | set(rows['team_away']) if (league, t) not in excluded)
        means = {side: np.array([getattr(states[t], f'{side}_mean') for t in teams]) for side in ('attack', 'defence')}
        sds = {side: np.sqrt([getattr(states[t], f'{side}_var') for t in teams]) for side in ('attack', 'defence')}
        centre = {side: float(means[side].mean()) for side in means}
        log = {side: means[side] - centre[side] for side in means}
        overall = np.exp(log['attack'] - log['defence'])
        ranks = dict(rank_attack=rank(log['attack'], True), rank_defence=rank(log['defence'], False),
                     rank_overall=rank(overall, True))
        records = []
        for i, team in enumerate(teams):
            record = dict(team=team, bar_label=BAR_LABEL)
            for side in ('attack', 'defence'):
                record.update({f'{side}_factor': float(np.exp(log[side][i])),
                               f'{side}_low': float(np.exp(log[side][i] - sds[side][i])),
                               f'{side}_high': float(np.exp(log[side][i] + sds[side][i])),
                               f'{side}_sd': float(sds[side][i]), f'{side}_mean_uncentred': float(means[side][i])})
            history_n, live_n = int(h_count.get(team, 0)), int(l_count.get(team, 0))
            record.update(overall=float(overall[i]), **{k: v[i] for k, v in ranks.items()},
                          matches_history=history_n, matches_2026_27=live_n, matches_total=history_n + live_n,
                          newcomer=history_n == 0)
            records.append(record)
        records.sort(key=lambda r: (r['rank_overall'], r['team']))
        leagues.append(dict(league=league, lower_defence_is_better=True, centre=centre, n_teams=len(teams),
                            bar_label=BAR_LABEL, defence_bar_note=DEFENCE_BAR_NOTE,
                            excluded=[f for f in flagged if f['league'] == league], teams=records))
    return leagues


def load_ratings(path=None):
    """ratings.json as written by run_ratings."""
    path = path or os.path.join(PROJECT_DIR, RESULTS, 'ratings.json')
    with open(path, encoding='utf-8') as handle:
        payload = json.load(handle)
    if 'leagues' not in payload:
        raise ValueError(f'{path} has no leagues')
    for league in payload['leagues']:
        if not {'league', 'lower_defence_is_better', 'teams', 'bar_label', 'defence_bar_note'} <= set(league):
            raise ValueError(f'ratings.json league object is missing fields: {sorted(league)}')
    return payload


def sd_matches_correlation(matches, attack_sd, defence_sd):
    """Spearman between matches played and each sd, with n."""
    out = {}
    for side, sd in (('attack', attack_sd), ('defence', defence_sd)):
        result = spearmanr(matches, sd)
        out[side] = dict(spearman=float(result.statistic), p_value=float(result.pvalue), n=len(matches))
    return out


def reading_sentence(spearman_attack, spearman_defence, n, display):
    """The reading of check 4, in the order: expectation, observed signs with Spearman, n."""
    held = spearman_defence < 0
    attack_falls = spearman_attack < 0
    return (f'The expectation that defence sd falls as matches played rises {"held" if held else "did not hold"}: '
            f'defence sd {"falls" if held else "rises"} with matches played (Spearman {display["spearman_defence"]}) '
            f'while attack sd {"falls" if attack_falls else "rises"} (Spearman {display["spearman_attack"]}); '
            f'n = {n} established teams.')


def ratings_checks(leagues):
    """The Phase 3 checks (their reading is written in ratings_check.md)."""
    centring = {lg['league']: max(abs(float(np.sum(np.log([t[f'{s}_factor'] for t in lg['teams']]))))
                                  for s in ('attack', 'defence')) for lg in leagues}
    top = {lg['league']: [t['team'] for t in lg['teams'][:3]] for lg in leagues}
    newcomers = []
    for lg in leagues:
        established = [t for t in lg['teams'] if not t['newcomer']]
        median = {s: float(np.median([t[f'{s}_sd'] for t in established])) for s in ('attack', 'defence')}
        newcomers += [dict(league=lg['league'], team=t['team'], matches_2026_27=t['matches_2026_27'],
                           **{f'{s}_sd': t[f'{s}_sd'] for s in ('attack', 'defence')},
                           **{f'league_median_{s}_sd': median[s] for s in ('attack', 'defence')},
                           larger=bool(all(t[f'{s}_sd'] > median[s] for s in ('attack', 'defence'))))
                      for t in lg['teams'] if t['newcomer']]
    established = [t for lg in leagues for t in lg['teams'] if not t['newcomer']]
    n = len(established)
    correlation = sd_matches_correlation([t['matches_total'] for t in established],
                                         [t['attack_sd'] for t in established],
                                         [t['defence_sd'] for t in established])
    defence_sd = [t['defence_sd'] for t in established]
    mde = Z95 / np.sqrt(n - 1)
    display = dict(
        n_established=str(n), spearman_attack=f'{correlation["attack"]["spearman"]:+.3f}',
        spearman_defence=f'{correlation["defence"]["spearman"]:+.3f}', smallest_significant_rho=f'{mde:.2f}',
        defence_sd_min=f'{min(defence_sd):.3f}', defence_sd_max=f'{max(defence_sd):.3f}',
        bar_factor_min=f'{np.exp(min(defence_sd)):.2f}', bar_factor_max=f'{np.exp(max(defence_sd)):.2f}',
        newcomers_larger=str(sum(x['larger'] for x in newcomers)), newcomers_n=str(len(newcomers)))
    return dict(max_abs_log_sum=centring, centring_tolerance=CENTRING_TOLERANCE, top3=top, newcomers=newcomers,
                sd_vs_matches=correlation, n_established=n, smallest_significant_rho=float(mde),
                defence_sd_range=[float(min(defence_sd)), float(max(defence_sd))],
                bar_factor_range=[float(np.exp(min(defence_sd))), float(np.exp(max(defence_sd)))],
                established_matches_range=[int(min(t['matches_total'] for t in established)),
                                           int(max(t['matches_total'] for t in established))],
                reading=reading_sentence(correlation['attack']['spearman'], correlation['defence']['spearman'], n,
                                         display),
                claims_display=display)


# ---------------------------------------------------------------- simulation: what the model implies

def round_robin(teams):
    """Double round robin by the circle method: a list of rounds, each a list of (home, away)."""
    teams = list(teams)
    rounds = []
    for _ in range(len(teams) - 1):
        rounds.append([(teams[i], teams[-1 - i]) for i in range(len(teams) // 2)])
        teams = [teams[0], teams[-1]] + teams[1:-1]
    return rounds + [[(away, home) for home, away in matches] for matches in rounds]


def simulate_matches(model, home_adv, seed=SIM_SEED, design=None):
    """Synthetic leagues, no real data. True strengths start from the model's prior (normal, initial_var) and take
    the model's random-walk step (variance process_noise) at every appearance; a team entering after the first season
    is drawn from the model's cold-start prior. Goals are Poisson with the model's rates (same clip). After each
    season the bottom teams by points then goal difference leave and are replaced (design constants, not fitted)."""
    design = dict(SIM_DESIGN, **(design or {}))
    rng = np.random.default_rng(seed)
    q_sd, prior_sd = np.sqrt(model['process_noise']), np.sqrt(model['initial_var'])
    low, high = model['rate_bounds']
    cold = np.array([-model['cold_attack'], model['cold_defence']])
    rows = []
    for league in range(design['leagues']):
        name, strength, serial = f'SIM{league}', {}, [0]

        def add_team(season):
            team = f'{name}-T{serial[0]}'
            serial[0] += 1
            strength[team] = (cold if season else 0.0) + rng.normal(0.0, prior_sd, 2)
            return team

        teams = [add_team(0) for _ in range(design['teams'])]
        for season in range(design['seasons']):
            label = f'{2020 + season}-{2021 + season}'
            points, difference = dict.fromkeys(teams, 0), dict.fromkeys(teams, 0)
            for number, matches in enumerate(round_robin(teams)):
                date = pd.Timestamp(SIM_START) + pd.DateOffset(years=season) + pd.Timedelta(days=7 * number)
                for home, away in matches:
                    for team in (home, away):
                        strength[team] = strength[team] + rng.normal(0.0, q_sd, 2)
                    lam = min(max(np.exp(strength[home][0] + strength[away][1] + home_adv), low), high)
                    mu = min(max(np.exp(strength[away][0] + strength[home][1]), low), high)
                    goals_home, goals_away = int(rng.poisson(lam)), int(rng.poisson(mu))
                    rows.append(dict(competition=name, season=label, date=date, team_home=home, team_away=away,
                                     goals_home=goals_home, goals_away=goals_away))
                    difference[home] += goals_home - goals_away
                    difference[away] += goals_away - goals_home
                    points[home] += 3 if goals_home > goals_away else int(goals_home == goals_away)
                    points[away] += 3 if goals_away > goals_home else int(goals_home == goals_away)
            order = sorted(teams, key=lambda t: (points[t], difference[t], t))
            leaving = set(order[:design['relegated']])
            teams = [t for t in teams if t not in leaving] + [add_team(season + 1) for _ in leaving]
    return pd.DataFrame(rows)


def simulation_result(frame, params, home_adv):
    """Run the frozen filter on the synthetic matches. Established teams: active in the last season and seen in an
    earlier one (the same rule as the real ratings, whose newcomers are absent from the earlier history)."""
    states, _ = final_states(frame, params, home_adv)
    last = frame['season'].max()
    now, before = frame.loc[frame['season'] == last], frame.loc[frame['season'] != last]
    active = set(now['team_home']) | set(now['team_away'])
    earlier = set(before['team_home']) | set(before['team_away'])
    teams = sorted(active & earlier)
    count = appearances(frame)
    correlation = sd_matches_correlation([int(count[t]) for t in teams],
                                         [float(np.sqrt(states[t].attack_var)) for t in teams],
                                         [float(np.sqrt(states[t].defence_var)) for t in teams])
    return dict(n_established=len(teams), n_matches=len(frame), sd_vs_matches=correlation,
                matches_range=[int(min(count[t] for t in teams)), int(max(count[t] for t in teams))])


def simulation_reading(real, sim):
    """Whether the synthetic teams show the real sign pattern (defence sd up, attack sd down with matches played)."""
    def pattern(c):
        return c['defence']['spearman'] > 0, c['attack']['spearman'] < 0
    same = pattern(real) == pattern(sim)
    if same and pattern(real) == (True, True):
        text = ('In the simulation the signs match the real teams: defence sd rises and attack sd falls with matches '
                "played. Under this design the filter's variance dynamics and the exit of the weakest teams each "
                'season both act, and the simulation does not separate the two.')
    elif same:
        text = 'In the simulation the signs match the real teams.'
    else:
        text = ('In the simulation the signs do not match the real teams, so this design does not reproduce the '
                'shape.')
    return same, text


def run_simulation(p2_params, model, home_adv, provenance, real_correlation, design=None, seed=SIM_SEED):
    design = dict(SIM_DESIGN, **(design or {}))
    result = simulation_result(simulate_matches(model, home_adv, seed, design), p2_params, home_adv)
    corr = result['sd_vs_matches']
    same, reading = simulation_reading(real_correlation, corr)
    display = dict(seed=str(seed), n_established=str(result['n_established']),
                   spearman_attack=f'{corr["attack"]["spearman"]:+.3f}',
                   spearman_defence=f'{corr["defence"]["spearman"]:+.3f}')
    return dict(label="WHAT THE MODEL IMPLIES: synthetic matches from the model's own prior; not a football finding",
                wording=WORDING, provenance=provenance, seed=seed, design=design,
                parameters=dict(p2_params, home_adv=home_adv), result=result, claims_display=display,
                same_sign_pattern_as_real=same, reading=reading)


# ---------------------------------------------------------------- ratings report

def md_list(items):
    return [f'- {item}' for item in items]


def ratings_text(payload):
    checks, prov, d = payload['checks'], payload['provenance'], payload['checks']['claims_display']
    sim = payload['simulation']
    sd = sim['claims_display']
    lines = ['# Team ratings: checks', '', WORDING, '',
             'DESCRIPTIVE: ratings from the final states of the frozen P2 goals-only filter run over H and the '
             f'2026-27 snapshot {SNAPSHOT_ISO}; no test, no claim.', '',
             f'Model: `results/p2/candidate_p2.json` (sha256 {prov["params_sha256"]}); code commit '
             f'{prov["code_commit"]} (fan_features.py sha256 {prov["fan_features_sha256"][:16]}..., differs from that '
             f'commit: {prov["fan_features_dirty"]}).', '',
             f'Every bar: {BAR_LABEL}.', '',
             "Factors: exp(posterior mean - centre), centre = mean of the posterior means over the league's active "
             '2026-27 teams. The model has no intercept, so uncentred values are not interpretable. An attack factor '
             'above one scores more than the league average side; a defence factor below one concedes less (lower '
             'is better). Overall = attack factor / defence factor. Bars are exp(centred mean plus or minus one sd) '
             "from the filter's own variance: a diagonal Gaussian (Laplace-style) approximation, centring "
             'uncertainty ignored, coverage not checked. Per-team factors, sds and ranks are in `ratings.json`.', '',
             '## Excluded teams (flagged aliases; names not merged)', '']
    lines += md_list(f'{f["league"]}: {f["team"]}, alias of {f["alias_of"] or "an earlier name"} '
                     f'(see `results/live2627/data_audit.md`)' for f in payload['excluded']) or ['- none']
    worst = max(checks['max_abs_log_sum'].values())
    lines += ['', '## 1. Factors average to one on the log scale within each league', '',
              f'Result: {"PASS" if worst < checks["centring_tolerance"] else "FAIL"} in all eight leagues '
              '(largest absolute sum of log factors, attack and defence, is below `CENTRING_TOLERANCE` in '
              '`fan_features.py`; the per-league values are in `ratings.json`).', '',
              '## 2. Top three per league by overall rank', '']
    lines += md_list(f'{league}: ' + ', '.join(names) for league, names in checks['top3'].items())
    lines += ['', 'The names are listed for reading by eye; this file does not judge them.', '',
              '## 3. Newcomer sd against the league median of established teams', '',
              f'{d["newcomers_larger"]} of {d["newcomers_n"]} newcomers have both the attack sd and the defence sd '
              "above their league's median for established teams (per-team values are in `ratings.json`).", '',
              '## 4. sd against matches played (established teams only)', '',
              checks['reading'], '',
              f'- attack: Spearman {d["spearman_attack"]} (n = {d["n_established"]})',
              f'- defence: Spearman {d["spearman_defence"]} (n = {d["n_established"]})',
              f'- Smallest |rho| that is significant at the usual two-sided level with n = {d["n_established"]} '
              f'established teams: about {d["smallest_significant_rho"]} (normal approximation, n minus one in the '
              'denominator). This is a significance threshold for established teams only, not a power calculation.',
              f'- Defence sd range across the established teams: {d["defence_sd_min"]} to {d["defence_sd_max"]} '
              f'(n = {d["n_established"]}), so the half-width factor of a defence bar ranges from '
              f'{d["bar_factor_min"]} to {d["bar_factor_max"]} times.', '',
              DEFENCE_BAR_NOTE, '',
              '## 5. What the model implies (simulation)', '',
              "Synthetic leagues with no real data, generated from the model's own prior and random walk with the "
              'fitted parameters, then filtered by the same frozen code. This shows what the model implies, not a '
              'football finding. The design constants and the seed are in `ratings_sim.json`.', '',
              f'- seed {sd["seed"]}',
              f'- defence: Spearman {sd["spearman_defence"]} (n = {sd["n_established"]} synthetic established teams)',
              f'- attack: Spearman {sd["spearman_attack"]} (n = {sd["n_established"]} synthetic established teams)', '',
              sim['reading'], '']
    return '\n'.join(lines) + '\n'


def run_ratings(frames, states, p2_params, model, home_adv, provenance):
    flagged = flagged_records(frames['names'])
    leagues = league_ratings(states, frames['history'], frames['live'], flagged)
    checks = ratings_checks(leagues)
    simulation = run_simulation(p2_params, model, home_adv, provenance, checks['sd_vs_matches'])
    payload = dict(label='DESCRIPTIVE: final filter states after the 2026-27 snapshot; no test, no claim',
                   wording=WORDING, provenance=provenance, lower_defence_is_better=True, bar_label=BAR_LABEL,
                   defence_bar_note=DEFENCE_BAR_NOTE,
                   interval='exp(centred mean minus sd) to exp(centred mean plus sd); approximate, coverage not checked',
                   centring="mean of posterior means over the league's active 2026-27 teams (flagged teams excluded)",
                   excluded=flagged, leagues=leagues, checks=checks)
    write_json('ratings.json', payload)
    write_json('ratings_sim.json', simulation)
    write_text('ratings_check.md', ratings_text(dict(payload, simulation=simulation)))
    return payload, simulation


# ---------------------------------------------------------------- outputs for the dashboard

def sample_rows(scored, count=SAMPLE_SIZE):
    """Evenly spaced positions of the live test set (deterministic)."""
    return scored.iloc[np.linspace(0, len(scored) - 1, count).astype(int)]


def run_outputs(frames, p2_params, model, home_adv, forecasts, provenance):
    """model_constants.json (what a browser implementation needs) and sample_forecasts.json (parity fixtures)."""
    constants = dict(
        label=DESCRIPTIVE, wording=WORDING, provenance=provenance, home_adv=home_adv, rho=model['rho'],
        rate_bounds=list(model['rate_bounds']), clip_rates=model['clip_rates'], process_noise=model['process_noise'],
        grid=dict(market_max_goals=MARKET_GOALS, model_max_goals=MODEL_GOALS, min_mass=MIN_MASS,
                  mass_check='Poisson product mass before the rho factors must be at least min_mass, else raise'),
        correction=dict(
            rule='multiply the four low-score cells, floor each factor at 0, renormalise the whole grid',
            cells={'0-0': '1 - lambda*mu*rho', '0-1': '1 + lambda*rho', '1-0': '1 + mu*rho', '1-1': '1 - rho'},
            source='exp_model.dixon_coles_probs'),
        markets=dict(over_line=OVER_LINE, over='P(total goals > over_line)', btts='P(home >= 1 and away >= 1)',
                     top_k=TOP_K, top_tie_break='probability descending, then home goals, then away goals'),
        params=p2_params, params_sha256=provenance['params_sha256'])
    write_json('model_constants.json', constants)
    rows = sample_rows(frames['scored'])
    samples = []
    for index, row in rows.iterrows():
        f = forecasts.loc[index]
        grid = score_grid(f['lambda_home'], f['mu_away'], model['rho'])
        samples.append(dict(date=str(row['date']), league=row['competition'], home=row['team_home'],
                            away=row['team_away'], goals_home=int(row['goals_home']), goals_away=int(row['goals_away']),
                            lambda_home=float(f['lambda_home']), mu_away=float(f['mu_away']),
                            model_1x2_max_goals_10=[float(f['pred_home_win']), float(f['pred_draw']),
                                                    float(f['pred_away_win'])],
                            markets=markets(grid)))
    write_json('sample_forecasts.json', dict(label=DESCRIPTIVE, wording=WORDING, provenance=provenance,
                                             purpose='parity fixtures: markets from lambda_home, mu_away and rho',
                                             rho=model['rho'], samples=samples))
    return constants, samples


# ---------------------------------------------------------------- main

def setup():
    frames = load_frames()
    p2_params, model, home_adv, p2_sha = load_model()
    states, forecasts = run_model(frames['both'], p2_params, home_adv)
    provenance = dict(code_provenance(), params_sha256=p2_sha, snapshot_date=SNAPSHOT_DATE)
    return frames, p2_params, model, home_adv, states, forecasts, provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--markets', action='store_true')
    parser.add_argument('--ratings', action='store_true')
    parser.add_argument('--outputs', action='store_true')
    args = parser.parse_args(argv)
    every = not (args.markets or args.ratings or args.outputs)
    frames, p2_params, model, home_adv, states, forecasts, provenance = setup()
    if args.markets or every:
        run_markets(frames, model, forecasts, provenance)
    if args.ratings or every:
        run_ratings(frames, states, p2_params, model, home_adv, provenance)
    if args.outputs or every:
        run_outputs(frames, p2_params, model, home_adv, forecasts, provenance)


if __name__ == '__main__':
    main()
