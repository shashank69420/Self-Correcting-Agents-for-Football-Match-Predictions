"""Stage 1: static time-decay-weighted Dixon-Coles baseline and its RPS evaluation."""
import numpy as np
import penaltyblog as pb


def fit_baseline(train_df):
    # Exponential Time-Decay Weighting
    print("\n[4/4] Fitting Dixon-Coles model with Time Decay (xi = 0.0065)...")
    max_date = train_df['date'].max()
    train_df['days_ago'] = (max_date - train_df['date']).dt.days
    train_df['decay_weight'] = np.exp(-0.0065 * train_df['days_ago'])

    clf = pb.models.DixonColesGoalModel(
        train_df["goals_home"],
        train_df["goals_away"],
        train_df["team_home"],
        train_df["team_away"],
        weights=train_df["decay_weight"]
    )
    clf.fit()
    print("  ✓ Model fitting successful.")
    return clf


def evaluate_baseline_rps(clf, test_df):
    # Calculate Out-of-Sample RPS
    rps_scores = []
    skipped_matches = 0

    for index, row in test_df.iterrows():
        try:
            probs = clf.predict(row['team_home'], row['team_away'])
            pred_h = probs.home_win
            pred_d = probs.draw

            actual_h_goals = row['goals_home']
            actual_a_goals = row['goals_away']

            if actual_h_goals > actual_a_goals:
                actual_h, actual_d = 1, 0
            elif actual_h_goals == actual_a_goals:
                actual_h, actual_d = 0, 1
            else:
                actual_h, actual_d = 0, 0

            rps = 0.5 * ((pred_h - actual_h)**2 + (pred_h + pred_d - (actual_h + actual_d))**2)
            rps_scores.append(rps)
        except ValueError:
            skipped_matches += 1

    avg_rps = np.mean(rps_scores)

    print("\n" + "=" * 60)
    print("OUT-OF-SAMPLE EVALUATION BENCHMARK")
    print("=" * 60)
    print(f"Evaluated Test Matches: {len(rps_scores)}")
    print(f"Skipped (Promoted Teams): {skipped_matches}")
    print(f"Calculated 2019-2026 Test RPS: {avg_rps:.4f}")
    print("=" * 60)
    return rps_scores, skipped_matches, avg_rps
