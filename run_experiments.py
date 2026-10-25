"""Greedy E1-E6 experiments on the Stage 2 filter. Selection uses DEV and VAL only; TEST is never scored.

python -X utf8 run_experiments.py --check     default params reproduce Stage 2 on all rows
python -X utf8 run_experiments.py --exp E1    one experiment on top of the incumbent (one pass)
python -X utf8 run_experiments.py --report    baseline vs frozen candidate P1 on DEV and VAL
python -X utf8 run_experiments.py --odds      read-only odds audit
"""
import argparse
import contextlib
import io
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

import exp_harness as harness
from data_pipeline import chronological_split, ingest_and_clean_fixtures
from exp_model import DEFAULT_PARAMS, apply_calibration, fit_calibration, make_params, run_filter
from stage2_dynamic import compute_home_adv, run_sequential_filter
from stage3_detector import run_change_filter

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(PROJECT_DIR, 'results', 'experiments')
EXPERIMENTS_MD = os.path.join(PROJECT_DIR, 'EXPERIMENTS.md')
FILTER_COLUMNS = ['date', 'team_home', 'team_away', 'goals_home', 'goals_away', 'season', 'competition']
ORDER = ['E1', 'E2', 'E3', 'E4', 'E5', 'E6']
GRID_LIMIT_SECONDS = 20 * 60
MAX_WORKERS = 12
GRIDS = {
    'E1': [dict(process_noise=q, initial_var=v) for q in (0.005, 0.01, 0.02, 0.04) for v in (0.3, 0.6, 1.0)],
    'E2': [dict(drift_per_day=d, season_var=s) for d in (0.0, 0.0002, 0.0005) for s in (0.0, 0.02, 0.05)],
    'E3': [dict(cold_attack=a, cold_defence=d, clip_rates=c)
           for a in (0.0, 0.15, 0.3) for d in (0.0, 0.15, 0.3) for c in (False, True)],
    'E4': [dict(league_k=k) for k in (None, 100, 300, 1000)],
    'E5': [dict(rho=r) for r in (0.0, -0.04, -0.08, -0.12, -0.16)],
    'E6': [dict(calibration='temperature + class bias, fitted on DEV')],
}
TITLES = {'E1': 'Hyperparameters', 'E2': 'Drift', 'E3': 'Cold start and rate clip', 'E4': 'League effects',
          'E5': 'Draw correction (Dixon-Coles rho)', 'E6': 'Recalibration'}


def load_data():
    with contextlib.redirect_stdout(io.StringIO()):
        df = ingest_and_clean_fixtures(refresh=False)
        train_df, test_df = chronological_split(df)
    home_adv = compute_home_adv(train_df, test_df)
    return df, train_df, test_df.index, home_adv


def forecast(frame, params, home_adv):
    return run_filter(frame, params, home_adv)[harness.PROB_COLUMNS]


def result_path(name, extension='json'):
    return os.path.join(RESULTS_DIR, f'{name}.{extension}')


def read_json(name):
    with open(result_path(name), encoding='utf-8') as handle:
        return json.load(handle)


def write_json(name, payload):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_path(name), 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, indent=2)


def jsonable(params):
    return {key: list(value) if isinstance(value, tuple) else value for key, value in params.items()}


def check_equality(df, test_index, home_adv):
    """Default params reproduce Stage 2 on all rows. Reports differences only, never a score."""
    exp = run_filter(df, DEFAULT_PARAMS, home_adv)
    stage2, _ = run_sequential_filter(df, home_adv)
    export, _ = run_change_filter(df, 0.0, home_adv=home_adv)
    if not (exp.index.equals(stage2.index) and exp.index.equals(export.index)):
        raise AssertionError('Row order differs from Stage 2.')
    if list(exp.columns) != list(export.columns):
        raise AssertionError(f'Columns differ from the Stage 2 export: {list(export.columns)}')
    probs = harness.PROB_COLUMNS
    diffs = {'probs vs run_sequential_filter': float(np.abs(exp[probs].to_numpy() - stage2[probs].to_numpy()).max()),
             'probs vs Stage 2 export': float(np.abs(exp[probs].to_numpy() - export[probs].to_numpy()).max()),
             'rates vs Stage 2 export': float(np.abs(exp[['lambda_home', 'mu_away']].to_numpy()
                                                     - export[['lambda_home', 'mu_away']].to_numpy()).max()),
             'other export columns': float(np.abs(exp[['surprise_score', 'extra_process_variance',
                                                       'max_extra_component_variance']].to_numpy()
                                                  - export[['surprise_score', 'extra_process_variance',
                                                            'max_extra_component_variance']].to_numpy()).max())}
    # TEST rows must not influence any earlier forecast.
    non_test = df.loc[~df.index.isin(test_index)]
    without_test = run_filter(non_test, DEFAULT_PARAMS, home_adv)
    diffs['non-TEST probs, with vs without TEST rows'] = float(
        np.abs(without_test[probs].to_numpy() - exp.loc[without_test.index, probs].to_numpy()).max())
    for name, value in diffs.items():
        print(f'  max abs diff, {name}: {value:.3e}')
    print(f'  rows compared: {len(exp)}; identical match columns: '
          f'{exp[["date", "team_home", "team_away"]].equals(export[["date", "team_home", "team_away"]])}')
    passed = max(diffs.values()) <= 1e-12 and (exp.lineup_available == export.lineup_available).all()
    print('EQUALITY CHECK:', 'PASSED' if passed else 'FAILED')
    if not passed:
        raise SystemExit(1)


def mean_log_loss(frame, test_index, probs):
    probs, actual = harness.scored(frame, test_index, probs)
    return float(harness.row_scores(probs, actual)['LogLoss'].mean())


def evaluate_grid(name, work, incumbent, home_adv):
    candidates = [make_params(incumbent['params'], **overrides) for overrides in GRIDS[name]]
    started = time.time()
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(forecast, work, params, home_adv) for params in candidates]
        results = []
        for future in futures:
            remaining = GRID_LIMIT_SECONDS - (time.time() - started)
            results.append(future.result(timeout=max(remaining, 1)))
    return candidates, results, time.time() - started


def run_experiment(name, df, test_index, home_adv):
    position = ORDER.index(name)
    if os.path.exists(result_path(name)):
        raise SystemExit(f'{name} already ran (one pass only): {result_path(name)}')
    if position > 0 and not os.path.exists(result_path(ORDER[position - 1])):
        raise SystemExit(f'Run {ORDER[position - 1]} first: the experiments are sequential.')
    incumbent = (read_json('incumbent') if position > 0
                 else dict(params=jsonable(DEFAULT_PARAMS), calibration=None, accepted=[]))
    incumbent['params'] = make_params(incumbent['params'])
    work = df.loc[~df.index.isin(test_index), FILTER_COLUMNS]
    harness.assert_no_test(work, test_index)
    splits = harness.split_index(df, test_index)
    dev, val = df.loc[splits['dev']], df.loc[splits['val']]
    both = df.loc[splits['dev'].union(splits['val'])].sort_values('date', kind='stable')

    base_probs = forecast(work, incumbent['params'], home_adv)
    if name == 'E6':
        started = time.time()
        temperature, bias = fit_calibration(*harness.scored(dev, test_index, base_probs.loc[dev.index]))
        calibrated = pd.DataFrame(apply_calibration(base_probs.to_numpy(), temperature, bias),
                                  index=base_probs.index, columns=harness.PROB_COLUMNS)
        candidates, results = [dict(temperature=temperature, bias=bias)], [calibrated]
        elapsed = time.time() - started
        ci_rows = val
    else:
        candidates, results, elapsed = evaluate_grid(name, work, incumbent, home_adv)
        ci_rows = both

    records = []
    for params, probs in zip(candidates, results):
        overrides = (params if name == 'E6'
                     else {key: params[key] for key in GRIDS[name][0]})
        records.append(dict(**{key: (str(value) if isinstance(value, list) else value)
                               for key, value in overrides.items()},
                            dev_logloss=mean_log_loss(dev, test_index, probs.loc[dev.index]),
                            val_logloss=mean_log_loss(val, test_index, probs.loc[val.index]),
                            dev_rps=harness.summary(dev, test_index, probs.loc[dev.index])['RPS'],
                            val_rps=harness.summary(val, test_index, probs.loc[val.index])['RPS']))
    table = pd.DataFrame(records)
    chosen = int(np.argmin(table.dev_logloss.to_numpy()))  # first minimum in grid order
    inc_dev = mean_log_loss(dev, test_index, base_probs.loc[dev.index])
    inc_val = mean_log_loss(val, test_index, base_probs.loc[val.index])

    probs_ci, actual = harness.scored(ci_rows, test_index, results[chosen].loc[ci_rows.index])
    base_ci, _ = harness.scored(ci_rows, test_index, base_probs.loc[ci_rows.index])
    delta = harness.row_scores(probs_ci, actual)['LogLoss'] - harness.row_scores(base_ci, actual)['LogLoss']
    low, high, p_value = harness.week_block_ci(delta, ci_rows['date'])
    accepted, checks = harness.accept(inc_dev, table.dev_logloss[chosen], inc_val, table.val_logloss[chosen], high)

    if name == 'E6':
        chosen_overrides = dict(temperature=candidates[0]['temperature'], bias=candidates[0]['bias'])
    else:
        chosen_overrides = {key: candidates[chosen][key] for key in GRIDS[name][0]}
    ci_label = 'VAL' if name == 'E6' else 'DEV+VAL'
    payload = dict(experiment=name, title=TITLES[name], verdict='ACCEPTED' if accepted else 'REJECTED',
                   grid=GRIDS[name], chosen=jsonable(chosen_overrides),
                   incumbent_params=jsonable(incumbent['params']),
                   incumbent_dev_logloss=inc_dev, incumbent_val_logloss=inc_val,
                   chosen_dev_logloss=float(table.dev_logloss[chosen]),
                   chosen_val_logloss=float(table.val_logloss[chosen]),
                   ci_rows=ci_label, n_dev=len(dev), n_val=len(val), n_ci=len(ci_rows),
                   mean_delta_logloss=float(delta.mean()), ci99=[low, high], p_one_sided=p_value,
                   checks={key: bool(value) for key, value in checks.items()},
                   seconds=round(elapsed, 1), candidates=table.to_dict(orient='records'))
    if elapsed > GRID_LIMIT_SECONDS:
        payload['note'] = 'Grid exceeded the 20-minute limit.'

    lines = [f'## {name}: {TITLES[name]} -- {payload["verdict"]}', '',
             f'Incumbent: `{json.dumps(accepted_overrides(incumbent))}`'
             + (f' + calibration `{json.dumps(incumbent["calibration"])}`' if incumbent['calibration'] else '') + ' '
             f'(empty = Stage 2 defaults). Grid run time {elapsed:.1f} s. All numbers are {harness.LABEL}.', '',
             harness.markdown_table(table, 6), '',
             f'Chosen (lowest DEV log-loss): `{json.dumps(jsonable(chosen_overrides))}`', '',
             f'| | DEV log-loss (n={len(dev)}) | VAL log-loss (n={len(val)}) |', '|---|---|---|',
             f'| incumbent | {inc_dev:.6f} | {inc_val:.6f} |',
             f'| chosen | {table.dev_logloss[chosen]:.6f} | {table.val_logloss[chosen]:.6f} |', '',
             f'Chosen minus incumbent log-loss on {ci_label} (n={len(ci_rows)}): {delta.mean():+.6f}; '
             f'99% paired week-block CI [{low:+.6f}, {high:+.6f}] (2000 resamples, seed 20261025); '
             f'one-sided bootstrap p = {p_value:.4f}.', '',
             *[f'- {key}: {"yes" if value else "NO"}' for key, value in checks.items()], '',
             f'Verdict: **{payload["verdict"]}**.', '']
    markdown = '\n'.join(lines)
    with open(result_path(name, 'md'), 'w', encoding='utf-8') as handle:
        handle.write(markdown)
    write_json(name, payload)

    if accepted:
        if name == 'E6':
            incumbent['calibration'] = chosen_overrides
        else:
            incumbent['params'] = make_params(incumbent['params'], **chosen_overrides)
        incumbent['accepted'] = incumbent['accepted'] + [name]
    incumbent['params'] = jsonable(incumbent['params'])
    write_json('incumbent', incumbent)
    print(markdown)


def accepted_overrides(incumbent):
    params = make_params(incumbent['params'])
    return {key: value for key, value in jsonable(params).items() if jsonable(DEFAULT_PARAMS)[key] != value}


def final_report(df, train_df, test_index, home_adv):
    missing = [name for name in ORDER if not os.path.exists(result_path(name))]
    if missing:
        raise SystemExit(f'Experiments not yet run: {missing}')
    incumbent = read_json('incumbent')
    work = df.loc[~df.index.isin(test_index), FILTER_COLUMNS]
    splits = harness.split_index(df, test_index)
    dev, val = df.loc[splits['dev']], df.loc[splits['val']]
    baseline = forecast(work, DEFAULT_PARAMS, home_adv)
    candidate = forecast(work, make_params(incumbent['params']), home_adv)
    calibration = incumbent['calibration']
    refit = None
    if calibration is not None:
        # Reported numbers use the DEV-fitted calibrator; the frozen P1 uses a DEV+VAL refit.
        candidate = pd.DataFrame(apply_calibration(candidate.to_numpy(), calibration['temperature'],
                                                   calibration['bias']),
                                 index=candidate.index, columns=harness.PROB_COLUMNS)
        raw = forecast(work, make_params(incumbent['params']), home_adv)
        both = df.loc[splits['dev'].union(splits['val'])]
        temperature, bias = fit_calibration(*harness.scored(both, test_index, raw.loc[both.index]))
        refit = dict(temperature=temperature, bias=bias, fitted_on='DEV+VAL')

    results = [read_json(name) for name in ORDER]
    adjusted = harness.holm([result['p_one_sided'] for result in results])
    summary = pd.DataFrame([dict(experiment=r['experiment'], chosen=json.dumps(r['chosen']),
                                 dev_logloss=r['chosen_dev_logloss'], val_logloss=r['chosen_val_logloss'],
                                 ci99=f"[{r['ci99'][0]:+.6f}, {r['ci99'][1]:+.6f}] ({r['ci_rows']})",
                                 p_one_sided=r['p_one_sided'], p_holm=float(p), verdict=r['verdict'])
                            for r, p in zip(results, adjusted)])
    climate = harness.climatology(train_df, test_index)
    frames = dict(DEV=dev, VAL=val)
    probs = {split: dict(Baseline=baseline.loc[rows.index].to_numpy(), Candidate=candidate.loc[rows.index].to_numpy())
             for split, rows in frames.items()}
    body = harness.report(frames, test_index, probs, climate, train_df)
    text = '\n'.join([
        '# Harness report: Stage 2 baseline vs frozen candidate P1', '',
        f'Accepted experiments: {incumbent["accepted"] or "none"}. P1 parameters: '
        f'`{json.dumps(accepted_overrides(incumbent))}`'
        + (f'; calibration (DEV fit, used below) `{json.dumps(calibration)}`' if calibration else '') + '.', '',
        'Holm adjustment over the six experiments (one-sided bootstrap p; acceptance used the locked rule):', '',
        harness.markdown_table(summary, 6), '', body])
    with open(result_path('harness_report', 'md'), 'w', encoding='utf-8') as handle:
        handle.write(text)
    p1 = dict(candidate='P1', accepted_experiments=incumbent['accepted'],
              params=accepted_overrides(incumbent), calibration=refit,
              note='Overrides of exp_model.DEFAULT_PARAMS; home_adv stays compute_home_adv(train_df, test_df).')
    write_json('candidate_p1', p1)
    print(text[:3000])


def odds_report(df, test_index):
    columns, overall, by_group = harness.odds_audit(df, test_index)
    non_test = df.loc[~df.index.isin(test_index)]
    counts = columns.groupby(['market', 'timing']).size().reset_index(name='columns')
    overall = overall.sort_values(['timing', 'missing_share'], kind='stable')
    usable = overall.loc[(overall.missing_share <= 0.02) & (overall.worst_league_season <= 0.10)]
    group_table = by_group.reset_index().rename(columns={'index': 'league season'})
    text = '\n'.join([
        '# Odds audit (read-only, for the next stage)', '',
        f'Scope: the {len(non_test)} non-TEST rows (to {non_test.date.max():%Y-%m-%d}). TEST rows are excluded by '
        'TEST_INDEX, so 2024-2025 is partial and 2025-2026 is absent. No odds are used in any model here.', '',
        'Classification rule: football-data puts a C after the bookmaker code for closing odds '
        '(e.g. avg_ch, psch, b365_ch); all other odds columns are non-closing. Columns were classified from an '
        'explicit list; every non-match column of the fixture frame is covered (unknown columns raise).', '',
        harness.markdown_table(counts), '',
        '## Every odds-like column', '',
        ', '.join(f'`{c}` ({m}; {t})' for c, m, t in columns.itertuples(index=False)), '',
        '## 1X2 triples: missing share (missing, non-numeric, or odds <= 1)', '',
        harness.markdown_table(overall, 4), '',
        'Descriptive usability screen (not a spec item): missing share <= 2% overall and <= 10% in every '
        f'league-season. Passing: {", ".join(f"`{t}`" for t in usable.triple) or "none"}.', '',
        '## Missing share by league-season', '',
        harness.markdown_table(group_table, 3), '',
        '## When were non-closing odds collected?', '',
        'Source attempted: football-data.co.uk `notes.txt` (https://www.football-data.co.uk/notes.txt and '
        'http://...), on 2026-10-25. Both returned a network-filter "Web Site Blocked" page from this machine; '
        'an archived copy (web.archive.org) was refused as bot traffic. No football-data note was read.', '',
        '**Timing cannot be established from a source read in this session.** The data itself carries no '
        'collection timestamp for any odds column. My unverified recollection is that the notes describe '
        'pre-closing odds as collected on Friday afternoons for weekend games and Tuesday afternoons for '
        'midweek games; this must be confirmed from notes.txt before the next stage relies on non-closing odds '
        'as information available at T-60 minutes. Closing odds are, by definition, later than T-60 and remain '
        'evaluation-only.', ''])
    with open(result_path('odds_audit', 'md'), 'w', encoding='utf-8') as handle:
        handle.write(text)
    print(harness.markdown_table(overall, 4))


def append_experiments_md(name):
    with open(result_path(name, 'md'), encoding='utf-8') as handle:
        section = handle.read()
    with open(EXPERIMENTS_MD, 'a', encoding='utf-8') as handle:
        handle.write('\n' + section)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--exp', choices=ORDER)
    group.add_argument('--report', action='store_true')
    group.add_argument('--odds', action='store_true')
    args = parser.parse_args()
    df, train_df, test_index, home_adv = load_data()
    if args.check:
        check_equality(df, test_index, home_adv)
    elif args.exp:
        run_experiment(args.exp, df, test_index, home_adv)
        append_experiments_md(args.exp)
    elif args.report:
        final_report(df, train_df, test_index, home_adv)
    else:
        odds_report(df, test_index)


if __name__ == '__main__':
    main()
