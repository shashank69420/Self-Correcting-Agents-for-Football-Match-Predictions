"""Stage 3: persistent change detector on top of the Stage 2 filter, plus the lineup hook."""
import numpy as np
import pandas as pd

from metrics import outcome_classes, probability_metrics
from stage2_dynamic import (PROCESS_NOISE, TeamState, match_prediction_probs,
                            predict_step, update_step)

# One ordinary Poisson update per match. Surprise never scales its gradient
# or Fisher information; persistent evidence can increase FUTURE process noise.
CHANGE_SCALE_CANDIDATES = (0.0, 0.25, 0.5, 1.0, 2.0)
PREDICTION_LEAD_MINUTES = 60
LINEUP_DELTA_LIMIT = 0.5


def prediction_surprise_score(pred_home_win, pred_draw, pred_away_win,
                              goals_home, goals_away):
    p_actual = (pred_home_win if goals_home > goals_away else
                pred_draw if goals_home == goals_away else pred_away_win)
    probs = np.array([pred_home_win, pred_draw, pred_away_win], dtype=float)
    entropy = -np.sum(probs * np.log(probs + 1e-9))
    return float(np.clip(-np.log(max(p_actual, 1e-6)) / (entropy + 1e-6), 0.2, 5.0))


class ChangeEvidence:
    """Bounded, signed evidence for one team's attack OR concession tendency."""
    def __init__(self):
        self.ewma = 0.0
        self.direction = 0
        self.run = 0
        self.count = 0
        self.recent_surprises = []
        self.boost = 0.0

    def observe(self, goals, rate, surprise):
        # Detector statistic only; never an extra parameter update.
        z = float(np.clip((goals - rate) / np.sqrt(max(rate, 1e-6)), -3.0, 3.0))
        self.ewma = 0.75 * self.ewma + 0.25 * z
        direction = int(np.sign(z)) if abs(z) >= 0.5 else 0
        self.run = self.run + 1 if direction != 0 and direction == self.direction else int(direction != 0)
        self.direction = direction
        self.count += 1
        self.recent_surprises = (self.recent_surprises + [surprise >= 1.5])[-5:]
        persistent = (self.count >= 5 and self.run >= 3
                      and sum(self.recent_surprises) >= 2
                      and abs(self.ewma) >= 0.5)
        self.boost = min(1.0, abs(self.ewma) / 2.0) if persistent else 0.5 * self.boost
        return persistent


def prepare_lineup_offsets(matches, adjustments=None):
    """Precomputed player-based log-rate deltas, keyed to real fixtures.

    Define LINEUP_ADJUSTMENTS as a DataFrame BEFORE running this model cell.
    Required: date, competition, team_home, team_away, available_at,
    ratings_asof, home_attack_delta, home_defence_delta, away_attack_delta,
    away_defence_delta. Defence effects use the concession-tendency sign.
    Effects must be estimated from past data. Timestamp checks cannot certify
    how external ratings were trained. All timestamps must use the fixture
    clock; naive values are interpreted as UTC. Normalize source clocks first.
    """
    result = pd.DataFrame(0.0, index=matches.index, columns=[
        'home_attack_delta', 'home_defence_delta', 'away_attack_delta', 'away_defence_delta'])
    result['lineup_available'] = False
    if adjustments is None or adjustments.empty:
        return result
    effects = list(result.columns[:4])
    keys = ['date', 'competition', 'team_home', 'team_away']
    required = keys + ['available_at', 'ratings_asof'] + effects
    if not set(required).issubset(adjustments.columns):
        raise ValueError('Lineup data missing columns: ' + str(sorted(set(required) - set(adjustments.columns))))
    supplied = adjustments[required].copy()
    if supplied.isna().any().any():
        raise ValueError('Lineup keys, timestamps and effects must be complete.')
    fixture_keys = matches[keys].copy()
    fixture_keys['date'] = pd.to_datetime(fixture_keys.date, utc=True)
    for name in ('date', 'available_at', 'ratings_asof'):
        supplied[name] = pd.to_datetime(supplied[name], utc=True, errors='raise')
        if supplied[name].isna().any():
            raise ValueError('Lineup timestamps must not parse to NaT.')
    if fixture_keys.duplicated(keys).any() or supplied.duplicated(keys).any():
        raise ValueError('Fixture and lineup keys must be unique; select one as-of snapshot per fixture.')
    values = supplied[effects].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (np.abs(values) > LINEUP_DELTA_LIMIT).any():
        raise ValueError('Lineup effects must be finite and bounded by LINEUP_DELTA_LIMIT.')
    cutoff = supplied.date - pd.Timedelta(minutes=PREDICTION_LEAD_MINUTES)
    if (supplied.available_at > cutoff).any() or (supplied.ratings_asof > cutoff).any():
        raise ValueError('Lineup/rating data was unavailable at the forecast cutoff.')
    fixture_index = pd.MultiIndex.from_frame(fixture_keys)
    positions = fixture_index.get_indexer(pd.MultiIndex.from_frame(supplied[keys]))
    if (positions < 0).any():
        raise ValueError('Lineup data contains an unmatched date/competition/team fixture key.')
    result.iloc[positions, :4] = values
    result.iloc[positions, 4] = True
    return result


def run_change_filter(matches, change_scale=0.0, home_adv_override=None, lineup_offsets=None,
                      home_adv=None):
    # home_adv was a closure variable of main() in the original; it is now passed in explicitly.
    if not np.isfinite(change_scale) or not 0.0 <= change_scale <= 2.0:
        raise ValueError('change_scale must be finite and in [0, 2].')
    advantage = home_adv if home_adv_override is None else float(home_adv_override)
    if not np.isfinite(advantage):
        raise ValueError('Home advantage must be finite.')
    if not matches.index.is_unique:
        raise ValueError('Unique match indices are required.')
    required = ['date', 'team_home', 'team_away', 'goals_home', 'goals_away']
    if matches[required].isna().any().any():
        raise ValueError('Incomplete match data.')
    goals = matches[['goals_home', 'goals_away']].to_numpy(dtype=float)
    if not np.isfinite(goals).all() or (goals < 0).any() or (goals != np.floor(goals)).any():
        raise ValueError('Goals must be finite nonnegative integers.')
    if (matches.team_home == matches.team_away).any():
        raise ValueError('A team cannot play itself.')
    ordered = matches.sort_values('date', kind='stable')
    if lineup_offsets is None:
        offsets = np.zeros((len(ordered), 4))
        available = np.zeros(len(ordered), bool)
    else:
        aligned = lineup_offsets.loc[ordered.index]
        offsets = aligned[['home_attack_delta', 'home_defence_delta',
                           'away_attack_delta', 'away_defence_delta']].to_numpy(float)
        available = aligned.lineup_available.to_numpy(bool)
        if not np.isfinite(offsets).all() or (np.abs(offsets) > LINEUP_DELTA_LIMIT).any():
            raise ValueError('Invalid prepared lineup offsets.')
    states, evidence, records = {}, {}, []
    for position, row in enumerate(ordered.itertuples()):
        for team in (row.team_home, row.team_away):
            if team not in states:
                states[team] = TeamState()
                evidence[team] = (ChangeEvidence(), ChangeEvidence())
        hs, aws = states[row.team_home], states[row.team_away]
        ha, hd = evidence[row.team_home]
        aa, ad = evidence[row.team_away]
        prior_boosts = np.array([ha.boost, hd.boost, aa.boost, ad.boost])
        # Future-prior variance: no mean shift, no same-result feedback.
        extra = PROCESS_NOISE * change_scale * prior_boosts
        predict_step(hs, PROCESS_NOISE)
        predict_step(aws, PROCESS_NOISE)
        hs.attack_var += extra[0]
        hs.defence_var += extra[1]
        aws.attack_var += extra[2]
        aws.defence_var += extra[3]
        delta = offsets[position]
        if not np.any(delta):
            prediction_home, prediction_away = hs, aws
        else:
            prediction_home, prediction_away = TeamState(), TeamState()
            prediction_home.attack_mean = hs.attack_mean + delta[0]
            prediction_home.defence_mean = hs.defence_mean + delta[1]
            prediction_away.attack_mean = aws.attack_mean + delta[2]
            prediction_away.defence_mean = aws.defence_mean + delta[3]
        lambda_home = np.exp(prediction_home.attack_mean + prediction_away.defence_mean + advantage)
        mu_away = np.exp(prediction_away.attack_mean + prediction_home.defence_mean)
        pred_h, pred_d, pred_a = match_prediction_probs(prediction_home, prediction_away, advantage)
        surprise = prediction_surprise_score(pred_h, pred_d, pred_a, row.goals_home, row.goals_away)
        records.append(dict(date=row.date, team_home=row.team_home, team_away=row.team_away,
                            goals_home=row.goals_home, goals_away=row.goals_away,
                            pred_home_win=pred_h, pred_draw=pred_d, pred_away_win=pred_a,
                            lambda_home=float(lambda_home), mu_away=float(mu_away),
                            surprise_score=surprise, extra_process_variance=float(extra.sum()),
                            max_extra_component_variance=float(extra.max()),
                            lineup_available=bool(available[position])))
        # The ONLY observation update: ordinary unscaled Poisson gradient/Fisher.
        update_step(hs, aws, row.goals_home, row.goals_away, lambda_home, mu_away)
        # Known lineup context is included in residuals; evidence affects later priors.
        ha.observe(row.goals_home, lambda_home, surprise)
        ad.observe(row.goals_home, lambda_home, surprise)
        aa.observe(row.goals_away, mu_away, surprise)
        hd.observe(row.goals_away, mu_away, surprise)
    return pd.DataFrame(records, index=ordered.index), states


def select_change_scale(training_rows):
    cuts = [int(len(training_rows) * value) for value in (.55, .70, .85, 1.)]
    if cuts[0] == 0 or any(b <= a for a, b in zip(cuts[:-1], cuts[1:])):
        raise ValueError('Insufficient chronological training data.')
    records = []
    cols = ['pred_home_win', 'pred_draw', 'pred_away_win']
    for fold, (start, end) in enumerate(zip(cuts[:-1], cuts[1:]), 1):
        prefix = training_rows.iloc[:start]
        advantage = float(np.log(prefix.goals_home.mean()) - np.log(prefix.goals_away.mean()))
        actual = training_rows.iloc[start:end]
        for scale in CHANGE_SCALE_CANDIDATES:
            forecasts, _ = run_change_filter(training_rows.iloc[:end], scale, advantage)
            values = probability_metrics(forecasts.loc[actual.index, cols], outcome_classes(actual))
            records.append(dict(fold=fold, scale=scale, n=len(actual), home_adv=advantage,
                                start=start, end=end, **values))
        print(f'  Change-detector validation fold {fold}/3 complete ({end-start} matches).')
    folds = pd.DataFrame(records)
    names = ['RPS', 'Brier', 'LogLoss', 'Accuracy']
    summary = []
    for scale in CHANGE_SCALE_CANDIDATES:
        rows = folds.loc[folds.scale == scale]
        values = np.average(rows[names], axis=0, weights=rows.n)
        summary.append(dict(scale=scale, **dict(zip(names, values))))
    summary = pd.DataFrame(summary)
    base = summary.iloc[0]
    eligible = (summary[['RPS', 'Brier', 'LogLoss']] <= base[['RPS', 'Brier', 'LogLoss']] + 1e-12).all(axis=1)
    eligible &= summary.Accuracy >= base.Accuracy - 1e-12
    summary['eligible'] = eligible
    best = summary.loc[eligible].sort_values(['RPS', 'scale'], kind='stable').iloc[0]
    return float(best.scale), summary, folds


def calibration_summary(probabilities, labels):
    records = []
    for cls, name in enumerate(('Home', 'Draw', 'Away')):
        p = np.asarray(probabilities)[:, cls]
        y = (labels == cls).astype(float)
        bins = np.minimum((p * 10).astype(int), 9)
        for group in range(10):
            mask = bins == group
            if mask.any():
                records.append(dict(outcome=name, bin=group, n=int(mask.sum()),
                                    forecast=float(p[mask].mean()), observed=float(y[mask].mean())))
    return pd.DataFrame(records)
