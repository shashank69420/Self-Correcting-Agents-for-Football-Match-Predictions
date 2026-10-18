"""
Project B12: 2019-2026 Data & Baseline Metric Extraction Script
Orchestrates Stage 1 (static Dixon-Coles), Stage 2 (sequential Bayesian filter)
and Stage 3 (persistent change detector) in the original order.
"""
import os

import numpy as np
import pandas as pd

from data_pipeline import chronological_split, ingest_and_clean_fixtures
from metrics import (brier_and_log_loss, outcome_classes, paired_week_block_ci,
                     probability_metrics, stage2_rps)
from stage1_baseline import evaluate_baseline_rps, fit_baseline
from stage2_dynamic import (PROCESS_NOISE, compute_home_adv, print_final_team_states,
                            run_sequential_filter)
from stage3_detector import (PREDICTION_LEAD_MINUTES, calibration_summary,
                             prediction_surprise_score, prepare_lineup_offsets,
                             run_change_filter, select_change_scale)

# Generated files go in a project-relative outputs/ folder.
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs')
STAGE2_CSV_PATH = os.path.join(OUTPUT_DIR, 'stage2_forecasts.csv')


def main(LINEUP_ADJUSTMENTS=None):
    print("=" * 60)
    print("PROJECT B12: EXTRACTING 2019-2026 DATASET METRICS")
    print("=" * 60)

    # Data pipeline
    df = ingest_and_clean_fixtures()
    train_df, test_df = chronological_split(df)

    # Stage 1: static Dixon-Coles baseline
    clf = fit_baseline(train_df)
    rps_scores, skipped_matches, avg_rps = evaluate_baseline_rps(clf, test_df)

    # STAGE 2: Sequential Dynamic Bayesian Model
    print("\n" + "=" * 60)
    print("STAGE 2: SEQUENTIAL DYNAMIC BAYESIAN FILTER")
    print("=" * 60)
    home_adv = compute_home_adv(train_df, test_df)
    print(f"Fixed training-only home_adv: {home_adv!r}")
    print(f"Constant process noise per team appearance: {PROCESS_NOISE}")
    stage2_predictions, final_team_states = run_sequential_filter(df, home_adv)

    # Intersect the requested date range with the actual held-out row IDs.
    # Date-only filtering could include training matches on the split date.
    test_date_mask = stage2_predictions["date"].between(
        test_df["date"].min(), test_df["date"].max(), inclusive="both"
    )
    stage2_test = stage2_predictions.loc[
        test_date_mask & stage2_predictions.index.isin(test_df.index)
    ].loc[test_df.index]
    pd.testing.assert_frame_equal(
        stage2_test[["date", "team_home", "team_away", "goals_home", "goals_away"]],
        test_df[["date", "team_home", "team_away", "goals_home", "goals_away"]],
        check_dtype=False,
    )

    stage2_all_test_rps = stage2_rps(stage2_test)

    # Stage 1 skips unseen teams. Restrict the primary comparison to those same
    # matches, without fitting or invoking any Stage 1 model in the dynamic filter.
    # Verify the count so an unrelated baseline ValueError cannot go unnoticed.
    stage1_known_teams = set(train_df["team_home"]) | set(train_df["team_away"])
    common_mask = (stage2_test["team_home"].isin(stage1_known_teams)
                   & stage2_test["team_away"].isin(stage1_known_teams))
    stage2_common_test = stage2_test.loc[common_mask]
    if len(stage2_common_test) != len(rps_scores):
        raise ValueError(
            "Known-team test rows do not match Stage 1's evaluated count; "
            "inspect its skipped matches before claiming an identical-match comparison."
        )
    stage2_common_rps = stage2_rps(stage2_common_test)

    common_goals_home = stage2_common_test["goals_home"].to_numpy()
    common_goals_away = stage2_common_test["goals_away"].to_numpy()
    common_actual_class = np.where(
        common_goals_home > common_goals_away, 0,
        np.where(common_goals_home == common_goals_away, 1, 2)
    )
    common_one_hot = np.eye(3)[common_actual_class]  # Home, draw, away.

    stage1_common_probs = []
    for row in stage2_common_test.itertuples():
        stage1_match_probs = clf.predict(row.team_home, row.team_away)
        stage1_common_probs.append([
            stage1_match_probs.home_win, stage1_match_probs.draw, stage1_match_probs.away_win
        ])
    stage1_common_probs = np.asarray(stage1_common_probs, dtype=float)
    stage2_common_probs = stage2_common_test[
        ["pred_home_win", "pred_draw", "pred_away_win"]
    ].to_numpy(dtype=float)
    stage1_brier, stage1_log_loss = brier_and_log_loss(stage1_common_probs, common_one_hot)
    stage2_brier, stage2_log_loss = brier_and_log_loss(stage2_common_probs, common_one_hot)

    print("\n" + "=" * 60)
    print(f"IDENTICAL-MATCH COMPARISON ({len(stage2_common_test)} matches)")
    print("=" * 60)
    print(f"{'':<10}{'RPS':>10}{'Brier':>10}{'LogLoss':>10}")
    print(f"{'Stage 1:':<10}{avg_rps:>10.4f}{stage1_brier:>10.4f}{stage1_log_loss:>10.4f}")
    print(f"{'Stage 2:':<10}{stage2_common_rps:>10.4f}{stage2_brier:>10.4f}{stage2_log_loss:>10.4f}")
    print(f"Stage 2 RPS on ALL {len(stage2_test)} held-out matches: {stage2_all_test_rps:.4f}")
    print(f"Stage 1 skipped {len(stage2_test) - len(stage2_common_test)} of those matches.")
    print("Stage 2 forecasts each match before updating, including during the test period.")

    print_final_team_states(df, final_team_states)

    print('STAGE 3 (RESEARCH MILESTONE): PERSISTENT CHANGE DETECTOR — CONSERVATIVE DESIGN, VALIDATED NULL RESULT')

    print('\n' + '=' * 70)
    print('STAGE 3: PERSISTENT CHANGE DETECTOR; SINGLE POISSON UPDATE')
    print('=' * 70)
    CHANGE_SCALE, change_validation, change_validation_folds = select_change_scale(train_df)
    print(change_validation.to_string(index=False, float_format=lambda x: f'{x:.7f}'))
    print(f'Selected CHANGE_SCALE: {CHANGE_SCALE:g}')
    if CHANGE_SCALE == 0.0:
        print('Validation selected ordinary process noise; detector scores are still recorded.')
        print('This conservative design is retained as a robustness milestone, not the active mechanism.')
    else:
        print(f'Per-component process variance is bounded between {PROCESS_NOISE:g} and {PROCESS_NOISE*(1+CHANGE_SCALE):g}.')
    print('Each match uses exactly one ordinary, unscaled observation update.')
    print('Evaluation is retrospective: this test period has been examined previously.')

    stage3_predictions, stage3_final_team_states = run_change_filter(df, CHANGE_SCALE, home_adv=home_adv)
    stage2_export = (stage3_predictions if CHANGE_SCALE == 0.0
                     else run_change_filter(df, 0.0, home_adv=home_adv)[0])
    STAGE2_FORECASTS = stage2_export.copy()
    TEST_START = test_df['date'].min()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stage2_export.to_csv(STAGE2_CSV_PATH, index=False)
    stage3_test = stage3_predictions.loc[test_df.index]
    stage3_common_test = stage3_test.loc[stage2_common_test.index]
    match_columns = ['date', 'team_home', 'team_away', 'goals_home', 'goals_away']
    pd.testing.assert_frame_equal(stage3_common_test[match_columns], stage2_common_test[match_columns], check_dtype=False)
    prob_columns = ['pred_home_win', 'pred_draw', 'pred_away_win']
    stage3_common_probs = stage3_common_test[prob_columns].to_numpy(float)
    stage3_metrics = probability_metrics(stage3_common_probs, common_actual_class)
    stage3_common_rps, stage3_brier, stage3_log_loss = [stage3_metrics[key] for key in ('RPS', 'Brier', 'LogLoss')]
    comparison = pd.DataFrame([
        dict(Model='Stage 1', **probability_metrics(stage1_common_probs, common_actual_class)),
        dict(Model='Stage 2', **probability_metrics(stage2_common_probs, common_actual_class)),
        dict(Model='Stage 3', **stage3_metrics),
    ])
    print(f'\nIDENTICAL-MATCH COMPARISON ({len(stage3_common_test)} matches)')
    print(comparison.to_string(index=False, float_format=lambda x: f'{x:.7f}'))
    print(f'Test matches with extra variance: {(stage3_test.extra_process_variance > 0).sum()}/{len(stage3_test)}')
    print(f'Raw surprise mean/max: {stage3_test.surprise_score.mean():.4f}/{stage3_test.surprise_score.max():.4f}')
    print(f'Max extra variance per component: {stage3_test.max_extra_component_variance.max():.6f}')

    # Optional real lineup integration. Missing data is explicitly unevaluated.
    lineup_offsets = prepare_lineup_offsets(df, LINEUP_ADJUSTMENTS)
    ablation = [dict(Model='Stage 2 baseline', Status='evaluated', **comparison.iloc[1].drop('Model').to_dict()),
                dict(Model='Baseline + change detector', Status='evaluated', **stage3_metrics)]
    lineup_predictions = combined_predictions = None
    if lineup_offsets.lineup_available.any():
        lineup_predictions, _ = run_change_filter(df, 0.0, lineup_offsets=lineup_offsets, home_adv=home_adv)
        combined_predictions, _ = run_change_filter(df, CHANGE_SCALE, lineup_offsets=lineup_offsets, home_adv=home_adv)
        for name, forecasts in [('Baseline + lineup', lineup_predictions),
                                 ('Baseline + lineup + detector', combined_predictions)]:
            values = probability_metrics(forecasts.loc[stage2_common_test.index, prob_columns], common_actual_class)
            ablation.append(dict(Model=name, Status='evaluated; partial lineup coverage possible', **values))
        covered = lineup_offsets.loc[stage2_common_test.index].lineup_available
        print(f'Lineup coverage on common test: {covered.sum()}/{len(covered)} at T-{PREDICTION_LEAD_MINUTES} minutes.')
        print('Detector scale is frozen from no-lineup validation; joint retuning remains separate.')
    else:
        for name in ('Baseline + lineup', 'Baseline + lineup + detector'):
            ablation.append(dict(Model=name, Status='NOT EVALUATED: no historical lineup data'))
    ablation = pd.DataFrame(ablation)
    print('\nFOUR-WAY ABLATION')
    print(ablation.to_string(index=False, float_format=lambda x: f'{x:.7f}'))

    if lineup_offsets.lineup_available.any():
        # Reuses the shared paired calendar-week bootstrap (metrics.paired_week_block_ci).
        def print_lineup_subset(label, ids):
            baseline_rows = stage2_common_test.loc[ids]
            actual = outcome_classes(baseline_rows)
            baseline_probs = baseline_rows[prob_columns].to_numpy(float)
            lineup_probs = lineup_predictions.loc[ids, prob_columns].to_numpy(float)
            baseline_metrics = probability_metrics(baseline_probs, actual)
            lineup_metrics = probability_metrics(lineup_probs, actual)
            print(f'  {label} (N={len(ids)}):')
            for name, values in [('Baseline', baseline_metrics), ('Baseline + lineup', lineup_metrics)]:
                print(f"    {name}: RPS={values['RPS']:.7f}, Brier={values['Brier']:.7f}, "
                      f"LogLoss={values['LogLoss']:.7f}, Accuracy={values['Accuracy']:.7f}")
            positions = np.arange(len(ids))
            one_hot = np.eye(3)[actual]
            log_loss_delta = (-np.log(np.clip(lineup_probs[positions, actual], 1e-15, 1.0))
                              + np.log(np.clip(baseline_probs[positions, actual], 1e-15, 1.0)))
            baseline_rps = np.mean((np.cumsum(baseline_probs, axis=1)[:, :2]
                                    - np.cumsum(one_hot, axis=1)[:, :2])**2, axis=1)
            lineup_rps = np.mean((np.cumsum(lineup_probs, axis=1)[:, :2]
                                  - np.cumsum(one_hot, axis=1)[:, :2])**2, axis=1)
            for name, delta in [('LogLoss (PRIMARY)', log_loss_delta),
                                ('RPS', lineup_rps - baseline_rps)]:
                ci = paired_week_block_ci(delta, baseline_rows.date)
                print(f'    Baseline + lineup minus Baseline {name}: {delta.mean():.7f}; '
                      f'95% paired week-block CI=[{ci[0]:.7f}, {ci[1]:.7f}]')

        effect_columns = ['home_attack_delta', 'home_defence_delta',
                          'away_attack_delta', 'away_defence_delta']
        common_offsets = lineup_offsets.loc[stage2_common_test.index]
        covered_ids = common_offsets.index[common_offsets.lineup_available]
        print('\nLINEUP SIGNIFICANCE ON IDENTICAL COMMON TEST MATCHES')
        print(f'  Covered rows: {len(covered_ids)}/{len(stage2_common_test)}')
        if len(covered_ids):
            material_mask = common_offsets.loc[covered_ids, effect_columns].abs().max(axis=1) > 0.05
            material_ids = covered_ids[material_mask.to_numpy()]
            print(f'  Share with max |delta| > 0.05: {len(material_ids)/len(covered_ids):.2%}')
            print_lineup_subset('Covered rows', covered_ids)
            if len(material_ids):
                print_lineup_subset('SECONDARY, DESCRIPTIVE: max |delta| > 0.05', material_ids)
            else:
                print('  SECONDARY, DESCRIPTIVE: max |delta| > 0.05 (N=0); metrics/CI N/A')
        else:
            print('  Share with max |delta| > 0.05: N/A; no covered common-test rows.')
            print('  Baseline vs Baseline + lineup metrics/CI: N/A (empty subset).')

    classification_results, calibration_results = {}, {}
    print('\nOUTCOME CLASSIFICATION AND CALIBRATION (Home / Draw / Away)')
    for name, p in [('Stage 1', stage1_common_probs), ('Stage 2', stage2_common_probs), ('Stage 3', stage3_common_probs)]:
        confusion = np.zeros((3, 3), dtype=int)
        np.add.at(confusion, (common_actual_class, p.argmax(axis=1)), 1)
        recall = np.divide(np.diag(confusion), confusion.sum(axis=1), out=np.zeros(3), where=confusion.sum(axis=1) > 0)
        classification_results[name] = dict(confusion=confusion, recall=recall)
        bins = calibration_summary(p, common_actual_class)
        calibration_results[name] = bins
        ece = {label: float(np.average(np.abs(g.forecast-g.observed), weights=g.n))
               for label, g in bins.groupby('outcome')}
        draw = (common_actual_class == 1).astype(float)
        draw_p = np.clip(p[:, 1], 1e-15, 1-1e-15)
        print(f'{name}: draw probability={p[:,1].mean():.4f}; actual draw rate={draw.mean():.4f}; '
              f'draw Brier={np.mean((p[:,1]-draw)**2):.4f}; '
              f'draw binary log-loss={-np.mean(draw*np.log(draw_p)+(1-draw)*np.log(1-draw_p)):.4f}')
        print('  Class calibration ECE:', ece)
        print('  Recall H/D/A:', recall, '\n  Confusion matrix (actual rows):\n', confusion)
    print('\nStage 3 reliability bins:')
    print(calibration_results['Stage 3'].to_string(index=False, float_format=lambda x: f'{x:.4f}'))

    # Closing odds: evaluation only, with later information than T-60 forecasts.
    # Source: https://www.football-data.co.uk/data (C columns denote closing odds).
    market_columns = ['avg_ch', 'avg_cd', 'avg_ca']
    market_comparison = None
    if set(market_columns).issubset(df.columns):
        odds = df.loc[stage2_common_test.index, market_columns].apply(pd.to_numeric, errors='coerce').to_numpy()
        market_mask = np.isfinite(odds).all(axis=1) & (odds > 1.0).all(axis=1)
        if market_mask.any():
            implied = 1.0 / odds[market_mask]
            market_probs = implied / implied.sum(axis=1, keepdims=True)
            market_comparison = pd.DataFrame([
                dict(Model='Market closing average (normalized)', **probability_metrics(market_probs, common_actual_class[market_mask])),
                dict(Model='Stage 2 on identical market rows', **probability_metrics(stage2_common_probs[market_mask], common_actual_class[market_mask])),
                dict(Model='Stage 3 on identical market rows', **probability_metrics(stage3_common_probs[market_mask], common_actual_class[market_mask])),
            ])
            print(f'\nCLOSING-MARKET BENCHMARK: {market_mask.sum()} identical rows; later-information comparison')
            print(market_comparison.to_string(index=False, float_format=lambda x: f'{x:.7f}'))
        else:
            print('Market benchmark unavailable: no valid closing-odds triples.')
    else:
        print('Market benchmark unavailable: closing-odds columns missing.')

    # Paired week-block intervals are never used for model selection.
    one_hot = np.eye(3)[common_actual_class]
    rps2_rows = np.mean((np.cumsum(stage2_common_probs, axis=1)[:, :2] - np.cumsum(one_hot, axis=1)[:, :2])**2, axis=1)
    rps3_rows = np.mean((np.cumsum(stage3_common_probs, axis=1)[:, :2] - np.cumsum(one_hot, axis=1)[:, :2])**2, axis=1)
    stage3_rps_delta_ci = paired_week_block_ci(rps3_rows-rps2_rows, stage3_common_test.date)
    print('\nStage 3 minus Stage 2 RPS: ', float(np.mean(rps3_rows-rps2_rows)))
    print('95% paired week-block bootstrap interval: ', stage3_rps_delta_ci)

    stage2_test_surprise = np.asarray([prediction_surprise_score(row.pred_home_win, row.pred_draw,
        row.pred_away_win, row.goals_home, row.goals_away) for row in stage2_test.itertuples()])
    top_n = max(1, int(np.ceil(.1 * len(stage2_test))))
    top_positions = np.argsort(-stage2_test_surprise, kind='stable')[:top_n]
    print(f'\nTop 10% most surprising matches (N={top_n}); retrospective subgroup, not causal evidence:')
    print(f'  Stage 2 RPS: {stage2_rps(stage2_test.iloc[top_positions]):.7f}')
    print(f'  Stage 3 RPS: {stage2_rps(stage3_test.iloc[top_positions]):.7f}')
    post_upset_results = []
    for horizon in (1, 5, 10):
        positions = set()
        for pos in top_positions:
            row = test_df.iloc[pos]
            later = test_df.iloc[pos+1:]
            affected = later.team_home.isin([row.team_home, row.team_away]) | later.team_away.isin([row.team_home, row.team_away])
            positions.update(later.index[affected][:horizon])
        ids = sorted(positions)
        if ids:
            post_upset_results.append(dict(next_team_appearances=horizon, n=len(ids),
                                           Stage2_RPS=stage2_rps(stage2_test.loc[ids]),
                                           Stage3_RPS=stage2_rps(stage3_test.loc[ids])))
    print('\nACTUAL SUBSEQUENT MATCHES AFTER UPSETS (deduplicated):')
    print(pd.DataFrame(post_upset_results).to_string(index=False, float_format=lambda x: f'{x:.7f}'))
    print('=' * 70)
    return STAGE2_FORECASTS, TEST_START


def export_sanity_checks(STAGE2_FORECASTS, TEST_START):
    # Notebook cell that followed main(); takes the STAGE2_FORECASTS / TEST_START that main() returns.
    f = STAGE2_FORECASTS
    print('rows:', len(f))
    print('has rate columns:', {'lambda_home', 'mu_away'} <= set(f.columns))
    print('NaNs in rates:', int(f[['lambda_home', 'mu_away']].isna().sum().sum()))
    print('lambda range:', f.lambda_home.min(), f.lambda_home.max())
    print('mu range:', f.mu_away.min(), f.mu_away.max())
    print('dates:', f.date.min(), '->', f.date.max())
    print('TEST_START:', TEST_START)
    print('csv saved:', os.path.exists(STAGE2_CSV_PATH))
    print('any lineup rows (must be False):', bool(f.lineup_available.any()))

    f = STAGE2_FORECASTS.copy()
    test = f[f.date >= TEST_START]
    print('TEST lambda range:', test.lambda_home.min(), test.lambda_home.max())
    print('TEST mu range:', test.mu_away.min(), test.mu_away.max())
    bad = (f.lambda_home > 6) | (f.mu_away > 6)
    print('rows with a rate above 6:', int(bad.sum()), 'of', len(f))
    print('  of which in the test period:', int(bad[f.date >= TEST_START].sum()))
    cols = ['date', 'team_home', 'team_away', 'goals_home', 'goals_away', 'lambda_home', 'mu_away']
    print(f.sort_values('lambda_home', ascending=False)[cols].head(8).to_string())
    print(f.sort_values('mu_away', ascending=False)[cols].head(5).to_string())


if __name__ == "__main__":
    STAGE2_FORECASTS, TEST_START = main()
    export_sanity_checks(STAGE2_FORECASTS, TEST_START)
