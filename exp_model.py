"""Experimental variants of the Stage 2 filter. DEFAULT_PARAMS reproduce Stage 2 exactly."""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

from stage2_dynamic import PROCESS_NOISE, TeamState, predict_step, update_step
from stage3_detector import prediction_surprise_score

DEFAULT_PARAMS = dict(
    process_noise=PROCESS_NOISE,  # E1: variance added per team appearance
    initial_var=1.0,              # E1: attack and defence variance of a new team
    drift_per_day=0.0,            # E2: extra variance per day since the team's last match
    drift_cap_days=30.0,          # E2: days counted at most
    season_gap_days=45.0,         # E2: a gap longer than this starts a new season
    season_var=0.0,               # E2: extra variance at a team's first match of a new season
    cold_attack=0.0,              # E3: late-arriving teams start at attack_mean = -cold_attack
    cold_defence=0.0,             # E3: and defence_mean = +cold_defence (concedes more)
    clip_rates=False,             # E3: clip lambda and mu in forecast and update
    rate_bounds=(0.15, 6.0),
    league_k=None,                # E4: pseudo-matches shrinking league effects; None is off
    rho=0.0,                      # E5: Dixon-Coles low-score factor, outcome probabilities only
)

EXPORT_COLUMNS = ['date', 'team_home', 'team_away', 'goals_home', 'goals_away',
                  'pred_home_win', 'pred_draw', 'pred_away_win', 'lambda_home', 'mu_away',
                  'surprise_score', 'extra_process_variance', 'max_extra_component_variance',
                  'lineup_available']


def make_params(base=None, **overrides):
    params = dict(DEFAULT_PARAMS if base is None else base)
    unknown = (set(params) | set(overrides)) - set(DEFAULT_PARAMS)
    if unknown:
        raise KeyError(f'Unknown parameters: {sorted(unknown)}')
    params.update(overrides)
    params['rate_bounds'] = tuple(params['rate_bounds'])
    return params


def dixon_coles_probs(lambda_home, mu_away, rho=0.0, max_goals=10):
    """Home/draw/away probabilities from the Poisson score grid.

    Sign convention (Dixon and Coles 1997): tau(0,0) = 1 - lambda*mu*rho, tau(0,1) = 1 + lambda*rho,
    tau(1,0) = 1 + mu*rho, tau(1,1) = 1 - rho, with (home goals, away goals). rho < 0 inflates
    0-0 and 1-1 and deflates 1-0 and 0-1. Factors are floored at 0 and the grid is renormalised.
    With rho = 0 this is exactly stage2_dynamic.match_prediction_probs.
    """
    if not np.isfinite([lambda_home, mu_away]).all():
        raise FloatingPointError("Non-finite pre-match goal rate.")
    goals = np.arange(max_goals + 1)
    grid = np.outer(poisson.pmf(goals, lambda_home), poisson.pmf(goals, mu_away))
    if rho != 0.0:
        grid[0, 0] *= max(1.0 - lambda_home * mu_away * rho, 0.0)
        grid[0, 1] *= max(1.0 + lambda_home * rho, 0.0)
        grid[1, 0] *= max(1.0 + mu_away * rho, 0.0)
        grid[1, 1] *= max(1.0 - rho, 0.0)
    grid_mass = grid.sum()
    if not np.isfinite(grid_mass) or grid_mass <= 0:
        raise FloatingPointError("The specified score grid has no finite positive mass.")
    grid /= grid_mass
    # Rows are home goals; columns are away goals.
    return float(np.tril(grid, k=-1).sum()), float(np.trace(grid)), float(np.triu(grid, k=1).sum())


class LeagueEffects:
    """Online per-league home advantage and goal level, as deviations from the online global means.

    Only matches committed before the current kickoff count. Shrinkage adds k pseudo-matches at
    the global mean, so a league with no history gets zero offsets and the baseline rates.
    """

    def __init__(self, k):
        self.k = float(k)
        self.league = {}
        self.total = np.zeros(3)  # matches, home goals, away goals
        self.pending = []

    def offsets(self, league):
        n, home, away = self.total
        if n == 0 or home <= 0 or away <= 0:
            return 0.0, 0.0
        global_home, global_away = home / n, away / n
        n_l, home_l, away_l = self.league.get(league, np.zeros(3))
        shrunk_home = (home_l + self.k * global_home) / (n_l + self.k)
        shrunk_away = (away_l + self.k * global_away) / (n_l + self.k)
        home_adv_offset = (np.log(shrunk_home) - np.log(shrunk_away)
                           - (np.log(global_home) - np.log(global_away)))
        level_offset = 0.5 * (np.log(shrunk_home) + np.log(shrunk_away)
                              - np.log(global_home) - np.log(global_away))
        return float(home_adv_offset), float(level_offset)

    def observe(self, league, goals_home, goals_away):
        # Held back until commit(): a match never informs another with the same kickoff.
        self.pending.append((league, goals_home, goals_away))

    def commit(self):
        for league, goals_home, goals_away in self.pending:
            values = np.array([1.0, goals_home, goals_away])
            self.league[league] = self.league.get(league, np.zeros(3)) + values
            self.total += values
        self.pending = []


def run_filter(df, params, home_adv):
    """Pre-match forecasts for every row of df, in the Stage 2 export's columns.

    home_adv is the fixed training-only value from stage2_dynamic.compute_home_adv.
    """
    params = make_params(params)
    if not df.index.is_unique:
        raise ValueError("Unique match indices are required for exact test alignment.")
    required = ["date", "team_home", "team_away", "goals_home", "goals_away"]
    if df[required].isna().any().any():
        raise ValueError("The filter requires complete dates, teams, and goals.")
    if (df["team_home"] == df["team_away"]).any():
        raise ValueError("A match must contain two different teams.")
    late_start = params['cold_attack'] != 0.0 or params['cold_defence'] != 0.0
    league_on = params['league_k'] is not None
    if late_start or league_on:
        if not {'competition', 'season'} <= set(df.columns):
            raise ValueError("Cold start and league effects need competition and season columns.")
        first_season = df.groupby('competition')['season'].min().to_dict()
    low, high = params['rate_bounds']
    q, rho = params['process_noise'], params['rho']

    # A stable sort retains Stage 1's existing order for equal timestamps.
    ordered = df.sort_values("date", kind="stable")
    day_number = ordered["date"].to_numpy().astype('datetime64[ns]').astype(np.int64) / 86_400e9
    leagues = ordered['competition'].to_numpy() if league_on or late_start else None
    seasons = ordered['season'].to_numpy() if late_start else None
    effects = LeagueEffects(params['league_k']) if league_on else None
    states, last_day, records = {}, {}, []
    current_date = None
    for position, row in enumerate(ordered.itertuples()):
        if effects is not None and row.date != current_date:
            effects.commit()
            current_date = row.date
        extras = []
        for team in (row.team_home, row.team_away):
            extra = 0.0
            if team not in states:
                state = TeamState()
                state.attack_var = params['initial_var']
                state.defence_var = params['initial_var']
                if late_start and seasons[position] != first_season[leagues[position]]:
                    state.attack_mean = -params['cold_attack']
                    state.defence_mean = params['cold_defence']
                states[team] = state
            else:
                gap = day_number[position] - last_day[team]
                extra = (params['drift_per_day'] * min(gap, params['drift_cap_days'])
                         + (params['season_var'] if gap > params['season_gap_days'] else 0.0))
            last_day[team] = day_number[position]
            extras.append(extra)
        home_state = predict_step(states[row.team_home], q)
        away_state = predict_step(states[row.team_away], q)
        if extras[0] or extras[1]:
            home_state.attack_var += extras[0]
            home_state.defence_var += extras[0]
            away_state.attack_var += extras[1]
            away_state.defence_var += extras[1]

        log_lambda = home_state.attack_mean + away_state.defence_mean + home_adv
        log_mu = away_state.attack_mean + home_state.defence_mean
        if effects is not None:
            home_adv_offset, level_offset = effects.offsets(leagues[position])
            log_lambda = log_lambda + home_adv_offset + level_offset
            log_mu = log_mu + level_offset
        lambda_home, mu_away = np.exp(log_lambda), np.exp(log_mu)
        if params['clip_rates']:
            lambda_home = min(max(lambda_home, low), high)
            mu_away = min(max(mu_away, low), high)
        pred_h, pred_d, pred_a = dixon_coles_probs(lambda_home, mu_away, rho)

        # Save the forecast before incorporating this match's observed score.
        records.append(dict(date=row.date, team_home=row.team_home, team_away=row.team_away,
                            goals_home=row.goals_home, goals_away=row.goals_away,
                            pred_home_win=pred_h, pred_draw=pred_d, pred_away_win=pred_a,
                            lambda_home=float(lambda_home), mu_away=float(mu_away),
                            surprise_score=prediction_surprise_score(
                                pred_h, pred_d, pred_a, row.goals_home, row.goals_away),
                            extra_process_variance=float(2 * extras[0] + 2 * extras[1]),
                            max_extra_component_variance=float(max(extras)),
                            lineup_available=False))
        update_step(home_state, away_state, row.goals_home, row.goals_away, lambda_home, mu_away)
        if effects is not None:
            effects.observe(leagues[position], row.goals_home, row.goals_away)
    return pd.DataFrame(records, index=ordered.index, columns=EXPORT_COLUMNS)


def _calibration_vector(theta):
    return np.exp(theta[0]), np.array([theta[1], theta[2], -(theta[1] + theta[2])])


def apply_calibration(probs, temperature, bias):
    """softmax(log p / T + b), with b a 3-vector summing to 0 (Home, Draw, Away)."""
    bias = np.asarray(bias, float)
    if bias.shape != (3,) or abs(bias.sum()) > 1e-9 or not temperature > 0:
        raise ValueError('Calibration needs T > 0 and a 3-value bias summing to 0.')
    logits = np.log(np.clip(np.asarray(probs, float), 1e-15, 1.0)) / temperature + bias
    logits -= logits.max(axis=1, keepdims=True)
    weights = np.exp(logits)
    return weights / weights.sum(axis=1, keepdims=True)


def fit_calibration(probs, actual_class):
    """Temperature and class bias minimising mean log-loss on the given rows."""
    actual_class = np.asarray(actual_class)
    positions = np.arange(len(actual_class))

    def loss(theta):
        temperature, bias = _calibration_vector(theta)
        calibrated = apply_calibration(probs, temperature, bias)
        return -np.mean(np.log(np.clip(calibrated[positions, actual_class], 1e-15, 1.0)))

    result = minimize(loss, np.zeros(3), method='L-BFGS-B')
    if not result.success:
        raise RuntimeError(f'Calibration fit failed: {result.message}')
    temperature, bias = _calibration_vector(result.x)
    return float(temperature), [float(value) for value in bias]
