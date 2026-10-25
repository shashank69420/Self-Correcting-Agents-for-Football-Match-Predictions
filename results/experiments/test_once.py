"""One-shot TEST scoring of frozen P1. Usage (from C:\\dev\\b12): python -X utf8 test_once.py primary|secondary.

Stage 'primary' computes and writes ONLY the pre-registered primary result. Stage 'secondary' is run afterwards.
exp_harness.scored/summary refuse TEST rows by design, so this script uses harness.row_scores, harness.market_probs,
harness.week_block_ci and metrics.probability_metrics directly (no model or harness code is changed).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())
import exp_harness as harness  # noqa: E402
from exp_model import DEFAULT_PARAMS, make_params, run_filter  # noqa: E402
from metrics import outcome_classes, probability_metrics  # noqa: E402
from run_experiments import FILTER_COLUMNS, load_data, read_json, result_path  # noqa: E402
from stage2_dynamic import run_sequential_filter  # noqa: E402

OUT = os.path.join('results', 'experiments', 'test_once.md')
LABEL = 'TEST, one-shot, retrospective (this window was examined during Stages 1-5 and P1 selection)'
SEED = 20261026
EXPECTED = dict(process_noise=0.005, initial_var=0.3, cold_defence=0.3, clip_rates=True, rho=-0.04)


def forecasts():
    df, train_df, test_index, home_adv = load_data()
    p1 = read_json('candidate_p1')
    params = p1['params']
    verdicts = {name: read_json(name)['verdict'] for name in ('E1', 'E2', 'E3', 'E4', 'E5', 'E6')}
    confirmed = (params == EXPECTED and p1['accepted_experiments'] == ['E1', 'E3', 'E5'] and p1['calibration'] is None
                 and verdicts == dict(E1='ACCEPTED', E2='REJECTED', E3='ACCEPTED', E4='REJECTED', E5='ACCEPTED',
                                      E6='REJECTED'))
    full = df[FILTER_COLUMNS]
    baseline = run_filter(full, DEFAULT_PARAMS, home_adv)
    candidate = run_filter(full, make_params(**params), home_adv)
    stage2, _ = run_sequential_filter(df, home_adv)
    equal = float(np.abs(baseline[harness.PROB_COLUMNS].to_numpy() - stage2[harness.PROB_COLUMNS].to_numpy()).max())
    return df, train_df, test_index, params, p1, verdicts, confirmed, baseline, candidate, equal


def primary():
    df, train_df, test_index, params, p1, verdicts, confirmed, baseline, candidate, equal = forecasts()
    if not confirmed or equal > 1e-12:
        raise SystemExit(f'Parameter/baseline confirmation failed: confirmed={confirmed}, baseline diff={equal}')
    test = df.loc[test_index]
    if len(test) != 3829:
        raise SystemExit(f'Expected 3829 TEST rows, found {len(test)}')
    actual = outcome_classes(test)
    base_loss = harness.row_scores(baseline.loc[test_index, harness.PROB_COLUMNS].to_numpy(float), actual)['LogLoss']
    cand_loss = harness.row_scores(candidate.loc[test_index, harness.PROB_COLUMNS].to_numpy(float), actual)['LogLoss']
    delta = cand_loss - base_loss
    low, high, _ = harness.week_block_ci(delta, test['date'], level=0.95, n_resamples=2000, seed=SEED)
    verdict = 'ACCEPTED as a TEST improvement' if high < 0 else 'NOT accepted (CI upper bound is not below 0)'
    lines = [f'# One-shot TEST scoring of frozen P1', '', f'**{LABEL}**', '',
             'Pre-registered rule (fixed before running): primary = 95% paired week-block bootstrap CI '
             '(2000 resamples, seed 20261026) on mean log-loss difference, P1 minus Stage 2 baseline, over all '
             '3829 TEST_INDEX rows. P1 is accepted as a TEST improvement only if the CI upper bound is below 0. '
             'Everything else is secondary and descriptive.', '',
             '## 1. Parameters', '', '```json', json.dumps(p1, indent=2), '```', '',
             f'Confirmed equal to the accepted set: {confirmed}. Accepted experiments {p1["accepted_experiments"]}; '
             f'verdicts {verdicts}; calibration {p1["calibration"]}. home_adv is the fixed Stage 2 value. '
             f'Baseline = `exp_model.run_filter` defaults, max abs probability difference to '
             f'`run_sequential_filter` over all 19,145 rows: {equal:.1e}.', '',
             '## 2. Primary result', '',
             f'- Rows: {len(test)} (selected by TEST_INDEX only)',
             f'- Mean log-loss difference, P1 minus baseline: {delta.mean():+.6f} '
             f'(baseline {base_loss.mean():.6f}, P1 {cand_loss.mean():.6f})',
             f'- 95% paired week-block CI: [{low:+.6f}, {high:+.6f}]',
             f'- **Verdict: {verdict}.**', '']
    with open(OUT, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines))
    print('\n'.join(lines[lines.index('## 2. Primary result'):]))
    print('Parameters confirmed:', confirmed)
    return verdict


def secondary():
    df, train_df, test_index, params, p1, verdicts, confirmed, baseline, candidate, equal = forecasts()
    test = df.loc[test_index]
    actual = outcome_classes(test)
    cols = harness.PROB_COLUMNS
    base_p = baseline.loc[test_index, cols].to_numpy(float)
    cand_p = candidate.loc[test_index, cols].to_numpy(float)
    known = set(train_df.team_home) | set(train_df.team_away)
    common = (test.team_home.isin(known) & test.team_away.isin(known)).to_numpy()
    lines = ['## 3. Secondary metrics (descriptive only)', '', f'{LABEL}.', '']

    def table(name, mask, extra=None):
        records = []
        if extra is not None:
            records.append(dict(model='Closing market', **probability_metrics(extra, actual[mask])))
        records += [dict(model='Baseline', **probability_metrics(base_p[mask], actual[mask])),
                    dict(model='P1', **probability_metrics(cand_p[mask], actual[mask]))]
        frame = pd.DataFrame(records)
        frame.insert(1, 'n', int(mask.sum()))
        return [f'### {name}', '', harness.markdown_table(frame, 6), ''], frame.set_index('model')

    block, _ = table('All TEST rows', np.ones(len(test), bool))
    lines += block
    block, _ = table(f'Common rows (teams seen in training; main.py comparison set)', common)
    lines += block
    for label, mask in (('All TEST rows', np.ones(len(test), bool)), ('Common rows', common)):
        d = harness.row_scores(cand_p[mask], actual[mask]), harness.row_scores(base_p[mask], actual[mask])
        low, high, _ = harness.week_block_ci(d[0]['LogLoss'] - d[1]['LogLoss'], test['date'][mask], level=0.95,
                                             n_resamples=2000, seed=SEED)
        lines.append(f'- {label} (n={int(mask.sum())}): log-loss P1 minus baseline {np.mean(d[0]["LogLoss"] - d[1]["LogLoss"]):+.6f}, '
                     f'95% week-block CI [{low:+.6f}, {high:+.6f}] (descriptive)')
    lines += ['']
    market, mask = harness.market_probs(test)
    block, frame = table(f'Closing-odds TEST rows ({int(mask.sum())} of {len(test)})', mask, market[mask])
    lines += block
    lines += ['Gap closed by P1 = (baseline - P1) / (baseline - market):', '', '| metric | baseline | P1 | market | gap closed |',
              '|---|---|---|---|---|']
    for metric in ('RPS', 'Brier', 'LogLoss'):
        b, p, m = (frame.loc[name, metric] for name in ('Baseline', 'P1', 'Closing market'))
        lines.append(f'| {metric} | {b:.6f} | {p:.6f} | {m:.6f} | {(b - p) / (b - m):.2%} |')
    lines += ['']
    with open(OUT, 'a', encoding='utf-8') as handle:
        handle.write('\n' + '\n'.join(lines))
    print('\n'.join(lines))


if __name__ == '__main__':
    {'primary': primary, 'secondary': secondary}[sys.argv[1]]()
