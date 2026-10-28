"""PP (plan item 3, pp/PREREGISTRATION_v2.md): the frozen P2 goals-only filter with a posterior-predictive forecast.

Same states, same parameters, same updates as p2_model.run_filter; only the forecast changes. At each match the home
log-rate m_h = attack(home) + defence(away) + home_adv has variance v_h = attack_var(home) + defence_var(away) from the
predicted states (after predict_step); the away log-rate likewise. Each log-rate is integrated independently over its
Gaussian with N-node Gauss-Hermite quadrature. Every node pair gets the baseline's rate clip and its Dixon-Coles grid,
normalised by its own mass as exp_model.dixon_coles_probs does; the PP grid is the node-weighted sum. The mean is not
re-centred, and the update still uses the plug-in rates, so the two forecasts share every state.

The sum is computed in separable form (the two rates are independent): cell (k, l) = sum_ij a_ik M_ij b_jl with
a_ik = w_i P(k | lambda_i), b_jl = w_j P(l | mu_j) and M_ij = 1 / mass_ij; only the four Dixon-Coles cells carry the
extra N x N factor tau_ij. N is chosen once, without outcomes, by select_nodes (v2 numerical rule).
"""
import numpy as np
import pandas as pd
from numpy.polynomial.hermite import hermgauss
from scipy.stats import poisson

import p2_model
from exp_model import dixon_coles_probs
from stage2_dynamic import TeamState, predict_step, update_step

MAX_GOALS = 10  # exp_model.dixon_coles_probs default
LADDER = (9, 21, 41, 81, 161, 301)
REFERENCE_NODES = 301
NODE_TOLERANCE = 1e-5  # about 5% of the half-width of the P2 S2 99% CI (pp/PREREGISTRATION_v2.md)
SELECTION_ROWS = 2000
SELECTION_SEED = 20261019
PP_COLUMNS = ['pp_home_win', 'pp_draw', 'pp_away_win']
OUTPUT_COLUMNS = p2_model.OUTPUT_COLUMNS + PP_COLUMNS + ['log_mean_home', 'log_var_home', 'log_mean_away',
                                                         'log_var_away']


def nodes_and_weights(nodes):
    """Gauss-Hermite nodes x_i and weights w_i / sqrt(pi), so E f(N(m, v)) = sum_i w_i f(m + sqrt(2 v) x_i)."""
    x, w = hermgauss(nodes)
    return x, w / np.sqrt(np.pi)


def node_rates(log_mean, log_var, x, bounds):
    rates = np.exp(log_mean + np.sqrt(2.0 * log_var) * x)
    return rates if bounds is None else np.clip(rates, bounds[0], bounds[1])


def pp_grid(log_mean_home, log_var_home, log_mean_away, log_var_away, rho, bounds, nodes):
    """Posterior-predictive score grid, rows home goals. bounds = (low, high) clips each node rate as the baseline
    clips its rates; None leaves them unclipped (baseline with clip_rates off)."""
    x, w = nodes_and_weights(nodes)
    lam = node_rates(log_mean_home, log_var_home, x, bounds)
    mu = node_rates(log_mean_away, log_var_away, x, bounds)
    if not (np.isfinite(lam).all() and np.isfinite(mu).all()):
        raise FloatingPointError("Non-finite pre-match goal rate.")
    goals = np.arange(MAX_GOALS + 1)
    home, away = poisson.pmf(goals, lam[:, None]), poisson.pmf(goals, mu[:, None])
    tau = np.ones((nodes, nodes, 2, 2))
    if rho != 0.0:
        tau[:, :, 0, 0] = np.maximum(1.0 - lam[:, None] * mu[None, :] * rho, 0.0)
        tau[:, :, 0, 1] = np.maximum(1.0 + lam * rho, 0.0)[:, None]
        tau[:, :, 1, 0] = np.maximum(1.0 + mu * rho, 0.0)[None, :]
        tau[:, :, 1, 1] = max(1.0 - rho, 0.0)
    corner = home[:, None, :2, None] * away[None, :, None, :2]  # undamped cells (0..1, 0..1) per node pair
    mass = np.outer(home.sum(axis=1), away.sum(axis=1)) + (corner * (tau - 1.0)).sum(axis=(2, 3))
    if not (np.isfinite(mass).all() and (mass > 0).all()):
        raise FloatingPointError("The specified score grid has no finite positive mass.")
    inverse = 1.0 / mass
    grid = (w[:, None] * home).T @ inverse @ (w[:, None] * away)
    grid[:2, :2] = np.einsum('i,j,ijkl->kl', w, w, corner * tau * inverse[:, :, None, None])
    return grid


def outcome_probs(grid):
    """(home, draw, away) read from a grid as exp_model.dixon_coles_probs reads it."""
    return float(np.tril(grid, k=-1).sum()), float(np.trace(grid)), float(np.triu(grid, k=1).sum())


def selection_rows(output):
    """The 2,000 fixed rows (seed 20261019) of a filter output in its stable date order."""
    rng = np.random.default_rng(SELECTION_SEED)
    return output.iloc[np.sort(rng.choice(len(output), SELECTION_ROWS, replace=False))]


def ladder_errors(rows, rho, bounds, ladder=LADDER, reference=REFERENCE_NODES):
    """Per ladder value: max |N-node minus reference| over every scoreline cell and home/draw/away on the rows."""
    errors = dict.fromkeys(ladder, 0.0)
    for row in rows.itertuples():
        state = (row.log_mean_home, row.log_var_home, row.log_mean_away, row.log_var_away, rho, bounds)
        exact = pp_grid(*state, reference)
        exact_probs = np.array(outcome_probs(exact))
        for nodes in ladder:
            grid = exact if nodes == reference else pp_grid(*state, nodes)
            error = max(np.abs(grid - exact).max(), np.abs(np.array(outcome_probs(grid)) - exact_probs).max())
            errors[nodes] = max(errors[nodes], float(error))
    return errors


def select_nodes(errors, tolerance=NODE_TOLERANCE, reference=REFERENCE_NODES):
    """Smallest ladder value below the reference whose error is below the tolerance, else the reference."""
    for nodes in sorted(errors):
        if nodes < reference and errors[nodes] < tolerance:
            return nodes
    return reference


def run_filter(df, params, home_adv, nodes):
    """p2_model.run_filter's loop and output, plus the PP forecast and the log-rate means and variances it used."""
    params, w = p2_model.split_params(params)
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
    bounds = (low, high) if params['clip_rates'] else None
    q, rho = params['process_noise'], params['rho']

    ordered = df.sort_values("date", kind="stable")
    y_home, y_away, weight = p2_model.effective_goals(ordered, w)
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

        # PP: the same predicted states, integrated over their variances. Nothing here feeds the update.
        log_mean_home = home_state.attack_mean + away_state.defence_mean + home_adv
        log_mean_away = away_state.attack_mean + home_state.defence_mean
        log_var_home = home_state.attack_var + away_state.defence_var
        log_var_away = away_state.attack_var + home_state.defence_var
        pp_h, pp_d, pp_a = outcome_probs(pp_grid(log_mean_home, log_var_home, log_mean_away, log_var_away, rho,
                                                 bounds, nodes))

        records.append((row.date, row.team_home, row.team_away, row.goals_home, row.goals_away,
                        pred_h, pred_d, pred_a, float(lambda_home), float(mu_away), float(weight[position]),
                        pp_h, pp_d, pp_a, log_mean_home, log_var_home, log_mean_away, log_var_away))
        update_step(home_state, away_state, y_home[position], y_away[position], lambda_home, mu_away)
    return pd.DataFrame(records, index=ordered.index, columns=OUTPUT_COLUMNS)
