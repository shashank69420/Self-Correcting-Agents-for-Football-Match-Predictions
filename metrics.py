"""Shared evaluation helpers used by the Stage 1, 2 and 3 comparisons."""
import numpy as np
import pandas as pd


def stage2_rps(rows):
    scores = []
    for row in rows.itertuples():
        pred_h, pred_d = row.pred_home_win, row.pred_draw
        actual_h_goals, actual_a_goals = row.goals_home, row.goals_away
        if actual_h_goals > actual_a_goals:
            actual_h, actual_d = 1, 0
        elif actual_h_goals == actual_a_goals:
            actual_h, actual_d = 0, 1
        else:
            actual_h, actual_d = 0, 0
        rps = 0.5 * ((pred_h - actual_h)**2 + (pred_h + pred_d - (actual_h + actual_d))**2)
        scores.append(rps)
    if not scores:
        raise ValueError("No matches are available for the requested RPS comparison.")
    return float(np.mean(scores))


# Additional metrics on the exact same rows used for the RPS comparison.
def brier_and_log_loss(predicted_probs, actual_one_hot):
    # Mean squared error across all three classes, then across matches.
    brier = float(np.mean((predicted_probs - actual_one_hot) ** 2))
    actual_probs = np.sum(predicted_probs * actual_one_hot, axis=1)
    log_loss = float(-np.mean(np.log(np.clip(actual_probs, 1e-15, 1.0))))
    return brier, log_loss


def probability_metrics(probabilities, actual_class):
    p = np.asarray(probabilities, float)
    if p.shape != (len(actual_class), 3) or not np.isfinite(p).all() or (p < 0).any():
        raise ValueError('Invalid Home/Draw/Away probability matrix.')
    if not np.allclose(p.sum(axis=1), 1.0, atol=1e-10):
        raise ValueError('Probabilities must sum to one.')
    actual = np.eye(3)[actual_class]
    rps = float(np.mean((np.cumsum(p, axis=1)[:, :2] - np.cumsum(actual, axis=1)[:, :2]) ** 2))
    brier, loss = brier_and_log_loss(p, actual)
    return dict(RPS=rps, Brier=brier, LogLoss=loss,
                Accuracy=float(np.mean(p.argmax(axis=1) == actual_class)))


def outcome_classes(rows):
    return np.where(rows.goals_home > rows.goals_away, 0,
                    np.where(rows.goals_home == rows.goals_away, 1, 2))


def paired_week_block_ci(delta, dates):
    week_ids = dates.dt.to_period('W').astype(str).to_numpy()
    weekly = pd.DataFrame(dict(week=week_ids, delta=delta)).groupby('week').delta.agg(['sum', 'count'])
    rng = np.random.default_rng(20260922)
    resamples = rng.integers(len(weekly), size=(2000, len(weekly)))
    bootstrap_delta = (weekly['sum'].to_numpy()[resamples].sum(axis=1)
                       / weekly['count'].to_numpy()[resamples].sum(axis=1))
    return np.quantile(bootstrap_delta, [.025, .975])
