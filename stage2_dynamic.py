"""Stage 2: sequential dynamic Bayesian filter over team attack/defence strengths."""
import numpy as np
import pandas as pd
from scipy.stats import poisson

PROCESS_NOISE = 0.01


class TeamState:
    """Independent Gaussian attack and concession-tendency beliefs."""

    def __init__(self):
        self.attack_mean = 0.0
        self.attack_var = 1.0
        self.defence_mean = 0.0
        self.defence_var = 1.0


def predict_step(state, process_noise=PROCESS_NOISE):
    state.attack_var += process_noise
    state.defence_var += process_noise
    return state


def match_prediction_probs(home_state, away_state, home_adv, max_goals=10):
    lambda_home = np.exp(
        home_state.attack_mean + away_state.defence_mean + home_adv
    )
    mu_away = np.exp(away_state.attack_mean + home_state.defence_mean)
    if not np.isfinite([lambda_home, mu_away]).all():
        raise FloatingPointError("Non-finite pre-match goal rate.")

    goals = np.arange(max_goals + 1)
    grid = np.outer(poisson.pmf(goals, lambda_home), poisson.pmf(goals, mu_away))
    grid_mass = grid.sum()
    if not np.isfinite(grid_mass) or grid_mass <= 0:
        raise FloatingPointError("The specified score grid has no finite positive mass.")
    grid /= grid_mass

    # Rows are home goals; columns are away goals.
    pred_home_win = float(np.tril(grid, k=-1).sum())
    pred_draw = float(np.trace(grid))
    pred_away_win = float(np.triu(grid, k=1).sum())
    return pred_home_win, pred_draw, pred_away_win


def update_step(home_state, away_state, goals_home, goals_away, lambda_home, mu_away):
    # Both updates for an observation use the SAME pre-match rate and gradient.
    home_gradient = goals_home - lambda_home
    away_gradient = goals_away - mu_away

    attack_home_precision = 1.0 / home_state.attack_var + lambda_home
    defence_away_precision = 1.0 / away_state.defence_var + lambda_home
    attack_away_precision = 1.0 / away_state.attack_var + mu_away
    defence_home_precision = 1.0 / home_state.defence_var + mu_away

    home_state.attack_mean += home_gradient / attack_home_precision
    home_state.attack_var = 1.0 / attack_home_precision
    away_state.defence_mean += home_gradient / defence_away_precision
    away_state.defence_var = 1.0 / defence_away_precision

    away_state.attack_mean += away_gradient / attack_away_precision
    away_state.attack_var = 1.0 / attack_away_precision
    home_state.defence_mean += away_gradient / defence_home_precision
    home_state.defence_var = 1.0 / defence_home_precision
    return home_state, away_state


def compute_home_adv(train_df, test_df):
    if train_df.empty or test_df.empty:
        raise ValueError("Both Stage 1 training and test sets must be nonempty.")
    train_home_mean = train_df["goals_home"].mean()
    train_away_mean = train_df["goals_away"].mean()
    if (not np.isfinite([train_home_mean, train_away_mean]).all()
            or train_home_mean <= 0 or train_away_mean <= 0):
        raise ValueError("Training goal means must be finite and positive for home_adv.")
    home_adv = float(np.log(train_home_mean) - np.log(train_away_mean))
    return home_adv


def run_sequential_filter(df, home_adv):
    # home_adv is fixed once from main()'s actual Stage 1 train_df (see compute_home_adv).
    if not df.index.is_unique:
        raise ValueError("Unique match indices are required for exact test alignment.")
    if df[["date", "team_home", "team_away", "goals_home", "goals_away"]].isna().any().any():
        raise ValueError("Stage 2 requires complete dates, teams, and goals.")
    goals_array = df[["goals_home", "goals_away"]].to_numpy(dtype=float)
    if (not np.isfinite(goals_array).all() or (goals_array < 0).any()
            or (goals_array != np.floor(goals_array)).any()):
        raise ValueError("Poisson observations must be finite nonnegative integer goals.")
    if (df["team_home"] == df["team_away"]).any():
        raise ValueError("A match must contain two different teams.")

    # A stable sort retains Stage 1's existing order for equal timestamps.
    ordered_df = df.sort_values("date", kind="stable")
    team_states = {}
    records = []
    for row in ordered_df.itertuples():
        if row.team_home not in team_states:
            team_states[row.team_home] = TeamState()
        if row.team_away not in team_states:
            team_states[row.team_away] = TeamState()

        home_state = predict_step(team_states[row.team_home], PROCESS_NOISE)
        away_state = predict_step(team_states[row.team_away], PROCESS_NOISE)
        lambda_home = np.exp(home_state.attack_mean + away_state.defence_mean + home_adv)
        mu_away = np.exp(away_state.attack_mean + home_state.defence_mean)
        pred_h, pred_d, pred_a = match_prediction_probs(home_state, away_state, home_adv)

        # Save the forecast before incorporating this match's observed score.
        records.append({
            "date": row.date,
            "team_home": row.team_home,
            "team_away": row.team_away,
            "goals_home": row.goals_home,
            "goals_away": row.goals_away,
            "pred_home_win": pred_h,
            "pred_draw": pred_d,
            "pred_away_win": pred_a,
        })
        home_state, away_state = update_step(
            home_state, away_state, row.goals_home, row.goals_away, lambda_home, mu_away
        )
        team_states[row.team_home] = home_state
        team_states[row.team_away] = away_state

    columns = ["date", "team_home", "team_away", "goals_home", "goals_away",
               "pred_home_win", "pred_draw", "pred_away_win"]
    return pd.DataFrame(records, index=ordered_df.index, columns=columns), team_states


def print_final_team_states(df, final_team_states):
    club_aliases = [
        ("Man City", {"man city", "manchester city", "manchester city fc"}),
        ("Real Madrid", {"real madrid", "real madrid cf"}),
        ("Bayern Munich", {"bayern munich", "bayern munchen", "bayern münchen", "bayern", "fc bayern munich"}),
        ("Paris SG", {"paris sg", "paris saint germain", "paris saint-germain", "psg"}),
        ("Juventus", {"juventus", "juventus fc"}),
    ]
    print("\nFINAL TEAM STATES (higher defence_mean means more concessions)")
    home_team_names = df["team_home"].unique()
    for club_label, aliases in club_aliases:
        matches = [name for name in home_team_names
                   if " ".join(str(name).casefold().replace("_", " ").replace("-", " ").split())
                   in aliases]
        if not matches:
            print(f"{club_label}: not present under the recognized team-name aliases")
        for name in matches:
            state = final_team_states[name]
            print(f"{name}: attack_mean={state.attack_mean!r}, defence_mean={state.defence_mean!r}, "
                  f"attack_var={state.attack_var!r}, defence_var={state.defence_var!r}")
    print("=" * 60)
