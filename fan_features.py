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
from scipy.stats import poisson

import exp_harness as harness
import exp_model
import live2627
import p2_model
from run_experiments import FILTER_COLUMNS

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS = 'results/fan'
SNAPSHOT_DATE = '20261026'
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

def write_json(name, payload):
    path = os.path.join(PROJECT_DIR, RESULTS, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write('\n')


def write_text(name, text):
    path = os.path.join(PROJECT_DIR, RESULTS, name)
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
    lines = header('Goal markets: calibration', payload['provenance'])
    c = payload['climatology']
    lines += [f'Forecasts: one run of the filter over the {payload["counts"]["concatenated"]:,} concatenated rows; a row\'s '
              'forecast uses only earlier rows. Markets come from the rho-corrected 30-goal score grid. Nothing was '
              'tuned or recalibrated. Half-widths are 95% normal approximations. No TEST_INDEX row is scored.', '',
              f'Climatology baseline: {c["n"]:,} H rows dated before 2020-07-01 (last {c["last_date"]}); over 2.5 rate '
              f'{c["over_2_5"]:.4f}, BTTS rate {c["btts"]:.4f}.', '']
    for set_name, title in (('live', 'Live 2026-27 test set'), ('val', 'VAL (H, 2023-07-01 onward, excluding TEST_INDEX)')):
        block = payload['calibration'][set_name]
        lines += [f'## {title}', '']
        summary = []
        for market, label in (('over_2_5', 'Over 2.5'), ('btts', 'BTTS')):
            b = block[market]
            summary.append(dict(market=label, n=b['n'], brier=b['brier'], brier_clim=b['brier_climatology'],
                                skill=b['brier_skill'], brier_diff=f'{b["brier_diff"]:+.4f} +/- {b["brier_diff_hw95"]:.4f}',
                                log_loss=b['log_loss'], log_loss_clim=b['log_loss_climatology'],
                                log_loss_diff=f'{b["log_loss_diff"]:+.4f} +/- {b["log_loss_diff_hw95"]:.4f}',
                                mean_pred=f'{b["mean_predicted"]:.4f} +/- {b["mean_predicted_hw95"]:.4f}',
                                observed=f'{b["observed"]:.4f} +/- {b["observed_hw95"]:.4f}'))
        lines += [md_table(summary, ['market', 'n', 'brier', 'brier_clim', 'skill', 'brier_diff', 'log_loss',
                                     'log_loss_clim', 'log_loss_diff', 'mean_pred', 'observed']), '',
                  'brier_diff and log_loss_diff: model minus climatology, mean per match +/- 95% half-width.', '']
        for market, label in (('over_2_5', 'Over 2.5'), ('btts', 'BTTS')):
            lines += [f'Reliability, {label} (10 equal-width bins):', '',
                      md_table(block[market]['reliability'], ['bin', 'n', 'mean_predicted', 'observed',
                                                             'observed_hw95']), '']
        s = block['scorelines']
        lines += ['Scorelines (n {:,}):'.format(s['n']), '', md_table(
            [dict(scoreline=k, hit_rate=f'{s[k]["hit_rate"]:.4f} +/- {s[k]["hit_rate_hw95"]:.4f}',
                  mean_predicted=f'{s[k]["mean_predicted"]:.4f} +/- {s[k]["mean_predicted_hw95"]:.4f}')
             for k in ('top1', 'top3')], ['scoreline', 'hit_rate', 'mean_predicted']), '',
                  'top1: the most likely scoreline; top3: the three most likely. mean_predicted is the mean model '
                  'probability of those same scorelines.', '']
    lines += ['## Grid diagnostic', '',
              f'Maximum absolute difference between 1X2 from the corrected 30-goal grid and the model\'s own max_goals '
              f'{MODEL_GOALS} forecast. A description, not a failure.', '']
    for set_name, d in payload['grid_diagnostic'].items():
        lines.append(f'- {set_name}: n {d["n"]:,}, max {d["max_abs_diff"]:.3e}, rows above {DIAGNOSTIC_FLAG}: '
                     f'{len(d["rows_above_0_01"])}')
        lines += [f'  - {r["date"]} {r["league"]}: {r["home"]} v {r["away"]}, lambda {r["lambda_home"]:.3f}, '
                  f'mu {r["mu_away"]:.3f}, diff {r["diff"]:.4f}' for r in d['rows_above_0_01']]
    return '\n'.join(lines) + '\n'


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
    write_json('markets_calibration.json', payload)
    write_text('markets_calibration.md', markets_text(payload))
    return payload


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
    args = parser.parse_args(argv)
    frames, p2_params, model, home_adv, states, forecasts, provenance = setup()
    run_markets(frames, model, forecasts, provenance)


if __name__ == '__main__':
    main()
