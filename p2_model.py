"""P2 goals-only filter: the exp_model filter (no drift, season variance or league effects) with an optional
shots-on-target term in the post-match update (S1). With shots_w = 0 it reproduces exp_model.run_filter.

The update calls stage2_dynamic.update_step with y_eff = (1 - w) * goals + w * c * SoT in place of the goals, so
the gradient is y_eff minus the pre-match rate and the Fisher information (the pre-match rate) is unchanged.
"""
import numpy as np
import pandas as pd

from exp_model import DEFAULT_PARAMS, dixon_coles_probs, make_params
from stage2_dynamic import TeamState, predict_step, update_step

SHOTS_MIN_MATCHES = 300
SOT_COLUMNS = ('hst', 'ast')
UNSUPPORTED = ('drift_per_day', 'season_var', 'league_k')
OUTPUT_COLUMNS = ['date', 'team_home', 'team_away', 'goals_home', 'goals_away',
                  'pred_home_win', 'pred_draw', 'pred_away_win', 'lambda_home', 'mu_away', 'shots_weight']


def split_params(params):
    """(exp_model parameter set with defaults filled in, shots weight w)."""
    overrides = dict(params)
    w = float(overrides.pop('shots_w', 0.0))
    if not 0.0 <= w <= 1.0:
        raise ValueError(f'shots_w must be in [0, 1], got {w}')
    model = make_params(**overrides)
    for key in UNSUPPORTED:
        if model[key] != DEFAULT_PARAMS[key]:
            raise ValueError(f'p2_model.run_filter does not support {key}; use exp_model.run_filter.')
    return model, w


def _sot(frame):
    if not set(SOT_COLUMNS) <= set(frame.columns):
        return np.full((len(frame), 2), np.nan)
    return frame[list(SOT_COLUMNS)].apply(pd.to_numeric, errors='coerce').to_numpy(float)


def _earlier_ratio(dates, goals, sot, usable, targets):
    """For each target date: (matches, goals / SoT) over usable rows dated strictly earlier."""
    order = np.argsort(dates[usable], kind='stable')
    usable_dates = dates[usable][order]
    goal_sum = np.concatenate([[0.0], np.cumsum(goals[usable][order])])
    sot_sum = np.concatenate([[0.0], np.cumsum(sot[usable][order])])
    count = np.searchsorted(usable_dates, targets, side='left')  # side='left': same-day rows excluded
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = goal_sum[count] / sot_sum[count]
    return count, ratio


def shots_scale(frame):
    """Goals per shot on target for every row: its league over strictly earlier matches with both SoT present
    (at least 300), else pooled over all leagues strictly earlier (at least 300), else NaN."""
    dates = frame['date'].to_numpy().astype('datetime64[ns]')
    sot = _sot(frame)
    has_sot = np.isfinite(sot).all(axis=1)
    goals = frame['goals_home'].to_numpy(float) + frame['goals_away'].to_numpy(float)
    total_sot = np.where(has_sot, sot.sum(axis=1), 0.0)
    count, scale = _earlier_ratio(dates, goals, total_sot, has_sot, dates)
    scale = np.where(count >= SHOTS_MIN_MATCHES, scale, np.nan)
    leagues = frame['competition'].to_numpy() if 'competition' in frame.columns else np.full(len(frame), '')
    for league in pd.unique(leagues):
        rows = leagues == league
        league_count, league_scale = _earlier_ratio(dates, goals, total_sot, has_sot & rows, dates[rows])
        scale[rows] = np.where(league_count >= SHOTS_MIN_MATCHES, league_scale, scale[rows])
    return scale


def effective_goals(frame, w):
    """(y_home, y_away, row weight). Row weight is 0 without both SoT or without a scale; then y = goals."""
    goals = frame[['goals_home', 'goals_away']].to_numpy(float)
    if w == 0.0:
        return goals[:, 0], goals[:, 1], np.zeros(len(frame))
    sot = _sot(frame)
    scale = shots_scale(frame)
    weight = np.where(np.isfinite(sot).all(axis=1) & np.isfinite(scale), w, 0.0)
    shots = np.where(weight[:, None] > 0, scale[:, None] * np.nan_to_num(sot), 0.0)
    y = np.where(weight[:, None] > 0, (1.0 - weight[:, None]) * goals + weight[:, None] * shots, goals)
    return y[:, 0], y[:, 1], weight


def run_filter(df, params, home_adv):
    """Pre-match forecasts for every row of df (index and stable date order as exp_model.run_filter)."""
    params, w = split_params(params)
    if not df.index.is_unique:
        raise ValueError("Unique match indices are required for exact test alignment.")
    required = ["date", "team_home", "team_away", "goals_home", "goals_away"]
    if df[required].isna().any().any():
        raise ValueError("The filter requires complete dates, teams, and goals.")
    if (df["team_home"] == df["team_away"]).any():
        raise ValueError("A match must contain two different teams.")
    late_start = params['cold_attack'] != 0.0 or params['cold_defence'] != 0.0
    if late_start:
        if not {'competition', 'season'} <= set(df.columns):
            raise ValueError("Cold start needs competition and season columns.")
        first_season = df.groupby('competition')['season'].min().to_dict()
    low, high = params['rate_bounds']
    q, rho = params['process_noise'], params['rho']

    ordered = df.sort_values("date", kind="stable")
    y_home, y_away, weight = effective_goals(ordered, w)
    leagues = ordered['competition'].to_numpy() if late_start else None
    seasons = ordered['season'].to_numpy() if late_start else None
    states, records = {}, []
    for position, row in enumerate(ordered.itertuples()):
        for team in (row.team_home, row.team_away):
            if team not in states:
                state = TeamState()
                state.attack_var = params['initial_var']
                state.defence_var = params['initial_var']
                if late_start and seasons[position] != first_season[leagues[position]]:
                    state.attack_mean = -params['cold_attack']
                    state.defence_mean = params['cold_defence']
                states[team] = state
        home_state = predict_step(states[row.team_home], q)
        away_state = predict_step(states[row.team_away], q)
        lambda_home = np.exp(home_state.attack_mean + away_state.defence_mean + home_adv)
        mu_away = np.exp(away_state.attack_mean + home_state.defence_mean)
        if params['clip_rates']:
            lambda_home = min(max(lambda_home, low), high)
            mu_away = min(max(mu_away, low), high)
        pred_h, pred_d, pred_a = dixon_coles_probs(lambda_home, mu_away, rho)

        # Save the forecast before incorporating this match's observed score or shots.
        records.append((row.date, row.team_home, row.team_away, row.goals_home, row.goals_away,
                        pred_h, pred_d, pred_a, float(lambda_home), float(mu_away), float(weight[position])))
        update_step(home_state, away_state, y_home[position], y_away[position], lambda_home, mu_away)
    return pd.DataFrame(records, index=ordered.index, columns=OUTPUT_COLUMNS)
