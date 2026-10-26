"""P2: fresh-season replication of P1 and three pre-registered improvements (p2/PREREGISTRATION.md).

python -X utf8 run_p2.py --fetch       Phase 2: fetch 2014-2019, write results/p2/data_audit.md (counts only)
python -X utf8 run_p2.py --check       p2_model with shots_w = 0 reproduces exp_model's P1 on all 19,145 rows
python -X utf8 run_p2.py --select S0   one selection experiment on DEV/VAL (S0, S1, S2 in order; one pass each)
python -X utf8 run_p2.py --freeze      Phase 4: results/p2/candidate_p2.json
python -X utf8 run_p2.py --fresh       Phase 5: the pre-registered tests on F, once (needs the committed freeze)
python -X utf8 run_p2.py --test-look   Phase 6: descriptive look at TEST_INDEX rows (after Phase 5)
"""
import argparse
import hashlib
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

import exp_harness as harness
import p2_data
import p2_model
import p2_stack
from exp_model import DEFAULT_PARAMS, make_params
from exp_model import run_filter as exp_run_filter
from metrics import outcome_classes, probability_metrics
from run_experiments import FILTER_COLUMNS, load_data

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(PROJECT_DIR, 'results', 'p2')
P1_PATH = os.path.join(PROJECT_DIR, 'results', 'experiments', 'candidate_p1.json')
P1_EXPECTED = dict(process_noise=0.005, initial_var=0.3, cold_defence=0.3, clip_rates=True, rho=-0.04)
COLUMNS = FILTER_COLUMNS + list(p2_model.SOT_COLUMNS)
SEED = 20261030
N_RESAMPLES = 2000
SELECT_LEVEL = 0.99
FRESH_LEVEL = 1 - 0.05 / 3  # 98.3%, Bonferroni for three tests
MAX_WORKERS = 12
ORDER = ['S0', 'S1', 'S2']
FIXED_S0 = dict(clip_rates=True, rho=-0.04, cold_attack=0.0)
GRIDS = {
    'S0': [dict(process_noise=q, initial_var=v, cold_defence=d, **FIXED_S0)
           for q in (0.0025, 0.005) for v in (0.15, 0.3) for d in (0.3, 0.45, 0.6)],
    'S1': [dict(shots_w=w) for w in (0.25, 0.5, 0.75)],
}
GRID_KEYS = {'S0': ['process_noise', 'initial_var', 'cold_defence'], 'S1': ['shots_w']}
TITLES = {'S0': 'Widened grid on P1', 'S1': 'Shots on target in the update',
          'S2': 'Stack with the snapshot market (Model+Market track)'}
LABEL = harness.LABEL
FRESH_LABEL = 'FRESH out-of-time (2015-16 to 2018-19), first scoring'
TEST_LABEL = 'DESCRIPTIVE: TEST is not fresh; no claim from this'


# ---------------------------------------------------------------- files

def path(name):
    return os.path.join(RESULTS_DIR, name)


def write_text(name, text):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(path(name), 'w', encoding='utf-8') as handle:
        handle.write(text)


def read_json(name):
    with open(path(name), encoding='utf-8') as handle:
        return json.load(handle)


def write_json(name, payload):
    write_text(name, json.dumps(payload, indent=2) + '\n')


def load_p1():
    with open(P1_PATH, encoding='utf-8') as handle:
        p1 = json.load(handle)
    if p1['params'] != P1_EXPECTED or p1['calibration'] is not None:
        raise SystemExit(f'candidate_p1.json differs from the frozen P1: {p1}')
    return dict(p1['params'])


def payload_sha(payload):
    blank = dict(payload, sha256='')
    return hashlib.sha256(json.dumps(blank, indent=2, sort_keys=True).encode('utf-8')).hexdigest()


def load_frozen(root=PROJECT_DIR):
    """The frozen candidates, after the committed-file guard and the self-hash check."""
    frozen_path = p2_data.require_frozen(root)
    with open(frozen_path, encoding='utf-8') as handle:
        frozen = json.load(handle)
    if payload_sha(frozen) != frozen['sha256']:
        raise SystemExit('candidate_p2.json sha256 does not match its content.')
    return frozen


# ---------------------------------------------------------------- frames and scores

def selection_frames(df, test_index):
    """Filter input (non-TEST rows only) and the DEV, VAL and DEV+VAL rows; TEST rows can never enter."""
    splits = harness.split_index(df, test_index)
    keep = [column for column in COLUMNS + list(p2_data.SNAPSHOT_TRIPLE) if column in df.columns]
    frames = dict(work=df.loc[~df.index.isin(test_index), keep],
                  dev=df.loc[splits['dev']], val=df.loc[splits['val']],
                  both=df.loc[splits['dev'].union(splits['val'])].sort_values('date', kind='stable'))
    for frame in frames.values():
        harness.assert_no_test(frame, test_index)
    return frames


def forecast(frame, params, home_adv):
    return p2_model.run_filter(frame, params, home_adv)[harness.PROB_COLUMNS]


def row_loss(rows, test_index, probs):
    probs, actual = harness.scored(rows, test_index, probs)
    return harness.row_scores(probs, actual)['LogLoss']


def scores(rows, test_index, probs):
    result = harness.summary(rows, test_index, probs)
    return dict(logloss=result['LogLoss'], rps=result['RPS'], brier=result['Brier'])


def decide(dev_incumbent, dev_candidate, val_incumbent, val_candidate, ci_high):
    """The pre-registered rule: DEV and VAL log-loss improve and the 99% CI upper bound is below 0."""
    return harness.accept(dev_incumbent, dev_candidate, val_incumbent, val_candidate, ci_high)


def week_ci(delta, dates, level):
    low, high, _ = harness.week_block_ci(np.asarray(delta), pd.Series(dates).reset_index(drop=True), level=level,
                                         n_resamples=N_RESAMPLES, seed=SEED)
    return low, high


def snapshot_market(frame, fallback):
    """(market probabilities as a frame over rows with snapshot odds, the column label per row)."""
    odds, columns = p2_data.snapshot_odds(frame, fallback=fallback)
    has = np.isfinite(odds).all(axis=1)
    market = pd.DataFrame(p2_stack.market_probs(odds[has]), index=frame.index[has], columns=harness.PROB_COLUMNS)
    return market, columns


def stack_probs(coef, model_probs, market):
    rows = market.index
    return pd.DataFrame(p2_stack.apply(coef, model_probs.loc[rows].to_numpy(), market.to_numpy()), index=rows,
                        columns=harness.PROB_COLUMNS)


def md_metrics(records, digits=6):
    return harness.markdown_table(pd.DataFrame(records), digits)


# ---------------------------------------------------------------- Phase 2 and the equality check

def fetch():
    raw, failures = p2_data.fetch_fresh()
    if len(raw):
        os.makedirs(os.path.dirname(p2_data.FRESH_PATH), exist_ok=True)
        raw.to_pickle(p2_data.FRESH_PATH)
    fresh = p2_data.clean_fresh(raw)
    text, missing_share = p2_data.audit(raw, failures, fresh)
    write_text('data_audit.md', text)
    print(text)
    if missing_share > p2_data.MAX_MISSING_SHARE:
        raise SystemExit(f'STOP: {missing_share:.1%} of league-seasons missing (limit 10%).')


def check(df, home_adv):
    """shots_w = 0 with P1 parameters reproduces exp_model's P1 forecasts on every row (no score is computed)."""
    p1 = load_p1()
    reference = exp_run_filter(df[COLUMNS], make_params(**p1), home_adv)
    ours = p2_model.run_filter(df[COLUMNS], dict(p1, shots_w=0.0), home_adv)
    columns = harness.PROB_COLUMNS + ['lambda_home', 'mu_away']
    same_order = ours.index.equals(reference.index)
    diff = float(np.abs(ours[columns].to_numpy() - reference[columns].to_numpy()).max()) if same_order else np.inf
    passed = same_order and diff <= 1e-12
    text = '\n'.join(['# P2 equality check', '',
                      f'p2_model.run_filter with shots_w = 0 and P1 parameters vs exp_model.run_filter P1 on all '
                      f'{len(df)} rows of the main data (forecasts only, no score): same row order {same_order}; '
                      f'max abs difference in probabilities and rates {diff:.3e} (tolerance 1e-12).', '',
                      f'EQUALITY CHECK: {"PASSED" if passed else "FAILED"}', ''])
    write_text('check.md', text)
    print(text)
    if not passed:
        raise SystemExit('STOP: the w = 0 equality failed.')


# ---------------------------------------------------------------- Phase 3: selection

def incumbent_for(name):
    position = ORDER.index(name)
    if os.path.exists(path(f'{name}.json')):
        raise SystemExit(f'{name} already ran (one pass only).')
    if position > 0 and not os.path.exists(path(f'{ORDER[position - 1]}.json')):
        raise SystemExit(f'Run {ORDER[position - 1]} first: the experiments are sequential.')
    if position == 0:
        return dict(params=dict(load_p1(), shots_w=0.0), accepted=[])
    return read_json('incumbent.json')


def finish(name, payload, lines, incumbent, accepted_overrides):
    if payload['verdict'] == 'ACCEPTED' and accepted_overrides is not None:
        incumbent['params'] = dict(incumbent['params'], **accepted_overrides)
    if payload['verdict'] == 'ACCEPTED':
        incumbent['accepted'] = incumbent['accepted'] + [name]
    write_text(f'{name}.md', '\n'.join(lines))
    write_json(f'{name}.json', payload)
    write_json('incumbent.json', incumbent)
    print('\n'.join(lines))


def verdict_lines(checks, verdict):
    return [*[f'- {key}: {"yes" if value else "NO"}' for key, value in checks.items()], '',
            f'Verdict: **{verdict}**.', '']


def run_goals_experiment(name, df, test_index, home_adv):
    incumbent = incumbent_for(name)
    frames = selection_frames(df, test_index)
    work, dev, val, both = frames['work'], frames['dev'], frames['val'], frames['both']
    candidates = [dict(incumbent['params'], **overrides) for overrides in GRIDS[name]]
    started = time.time()
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(forecast, work, params, home_adv) for params in [incumbent['params']] + candidates]
        base, *results = [future.result() for future in futures]
    elapsed = time.time() - started

    records = []
    for params, probs in zip(candidates, results):
        dev_scores, val_scores = scores(dev, test_index, probs.loc[dev.index]), scores(val, test_index, probs.loc[val.index])
        records.append({**{key: params[key] for key in GRID_KEYS[name]},
                        **{f'dev_{k}': v for k, v in dev_scores.items()}, **{f'val_{k}': v for k, v in val_scores.items()}})
    table = pd.DataFrame(records)
    chosen = int(np.argmin(table.dev_logloss.to_numpy()))  # first minimum in grid order
    inc_dev, inc_val = scores(dev, test_index, base.loc[dev.index]), scores(val, test_index, base.loc[val.index])
    delta = (row_loss(both, test_index, results[chosen].loc[both.index])
             - row_loss(both, test_index, base.loc[both.index]))
    low, high = week_ci(delta, both['date'], SELECT_LEVEL)
    accepted, checks = decide(inc_dev['logloss'], table.dev_logloss[chosen], inc_val['logloss'],
                              table.val_logloss[chosen], high)
    verdict = 'ACCEPTED' if accepted else 'REJECTED'
    chosen_overrides = {key: candidates[chosen][key] for key in GRID_KEYS[name]}
    per_league = harness.grouped_metrics(val, test_index, {'incumbent': base.loc[val.index].to_numpy(),
                                                          'chosen': results[chosen].loc[val.index].to_numpy()},
                                         'competition')
    payload = dict(experiment=name, title=TITLES[name], verdict=verdict, grid=GRIDS[name], chosen=chosen_overrides,
                   incumbent_params=incumbent['params'], incumbent_dev=inc_dev, incumbent_val=inc_val,
                   chosen_dev={k: float(table[f'dev_{k}'][chosen]) for k in inc_dev},
                   chosen_val={k: float(table[f'val_{k}'][chosen]) for k in inc_val},
                   n_dev=len(dev), n_val=len(val), n_ci=len(both), mean_delta_logloss=float(delta.mean()),
                   ci99=[low, high], seed=SEED, checks={k: bool(v) for k, v in checks.items()},
                   seconds=round(elapsed, 1), candidates=table.to_dict(orient='records'),
                   val_per_league=per_league.to_dict(orient='records'))
    lines = [f'## {name}: {TITLES[name]} -- {verdict}', '',
             f'Incumbent: `{json.dumps(incumbent["params"])}` (accepted so far: {incumbent["accepted"] or "none"}). '
             f'Run time {elapsed:.1f} s. All numbers are {LABEL}.', '',
             harness.markdown_table(table, 6), '',
             f'Chosen (lowest DEV log-loss, first in grid order): `{json.dumps(chosen_overrides)}`', '',
             f'| | DEV log-loss | DEV RPS | DEV Brier | VAL log-loss | VAL RPS | VAL Brier |',
             '|---|---|---|---|---|---|---|',
             *[f'| {label} (DEV n={len(dev)}, VAL n={len(val)}) | {d["logloss"]:.6f} | {d["rps"]:.6f} | '
               f'{d["brier"]:.6f} | {v["logloss"]:.6f} | {v["rps"]:.6f} | {v["brier"]:.6f} |'
               for label, d, v in (('incumbent', inc_dev, inc_val),
                                   ('chosen', payload['chosen_dev'], payload['chosen_val']))], '',
             f'Chosen minus incumbent log-loss on DEV+VAL (n={len(both)}): {delta.mean():+.6f}; 99% paired '
             f'week-block CI [{low:+.6f}, {high:+.6f}] (2000 resamples, seed {SEED}).', '',
             *verdict_lines(checks, verdict),
             '### VAL per league', '', harness.markdown_table(per_league, 6), '']
    finish(name, payload, lines, incumbent, chosen_overrides)


def run_stack_experiment(df, test_index, home_adv):
    name = 'S2'
    incumbent = incumbent_for(name)
    frames = selection_frames(df, test_index)
    work, dev, val, both = frames['work'], frames['dev'], frames['val'], frames['both']
    model = forecast(work, incumbent['params'], home_adv)
    market, columns = snapshot_market(work, fallback=False)
    if not set(columns[columns != '']) <= {'/'.join(p2_data.SNAPSHOT_TRIPLE)}:
        raise SystemExit('Unexpected snapshot columns on the main data.')
    has = work.index.isin(market.index)
    full_market = np.full((len(work), 3), np.nan)
    full_market[has] = market.to_numpy()
    actual = outcome_classes(work)
    fits = {}
    for label, with_model in (('stack', True), ('market-only', False)):
        fits[label] = p2_stack.fit_dev(work['date'], model.to_numpy(), full_market, actual, has, with_model)
    fit_rows = work.index[p2_stack.dev_mask(work['date'], has)]
    if not fit_rows.isin(dev.index).all() or fits['stack']['n'] != len(fit_rows):
        raise AssertionError('The S2 fit used rows outside DEV.')
    probs = dict(stack=stack_probs(fits['stack'], model, market), market=stack_probs(fits['market-only'], model, market),
                 model=model.loc[market.index])
    rows = {split: frame.loc[frame.index.isin(market.index)] for split, frame in (('dev', dev), ('val', val), ('both', both))}
    if not len(rows['dev']):
        raise SystemExit('STOP: no snapshot odds on DEV.')
    table = {split: {label: scores(frame, test_index, p.loc[frame.index]) for label, p in probs.items()}
             for split, frame in rows.items()}
    delta = (row_loss(rows['both'], test_index, probs['stack'].loc[rows['both'].index])
             - row_loss(rows['both'], test_index, probs['market'].loc[rows['both'].index]))
    low, high = week_ci(delta, rows['both']['date'], SELECT_LEVEL)
    accepted, checks = decide(table['dev']['market']['logloss'], table['dev']['stack']['logloss'],
                              table['val']['market']['logloss'], table['val']['stack']['logloss'], high)
    verdict = 'ACCEPTED' if accepted else 'REJECTED'
    per_league = harness.grouped_metrics(rows['val'], test_index,
                                         {label: probs[label].loc[rows['val'].index].to_numpy()
                                          for label in ('market', 'stack')}, 'competition')
    snapshot = '/'.join(p2_data.SNAPSHOT_TRIPLE)
    payload = dict(experiment=name, title=TITLES[name], verdict=verdict, incumbent_params=incumbent['params'],
                   snapshot_columns=list(p2_data.SNAPSHOT_TRIPLE), stack_dev_fit=fits['stack'],
                   market_only_dev_fit=fits['market-only'],
                   n_rows={split: len(frame) for split, frame in rows.items()},
                   n_without_snapshot={'dev': len(dev) - len(rows['dev']), 'val': len(val) - len(rows['val'])},
                   scores=table, mean_delta_logloss=float(delta.mean()), ci99=[low, high], seed=SEED,
                   checks={k: bool(v) for k, v in checks.items()}, val_per_league=per_league.to_dict(orient='records'))
    lines = [f'## {name}: {TITLES[name]} -- {verdict}', '',
             f'Goals-only model: `{json.dumps(incumbent["params"])}`. Snapshot triple `{snapshot}` (non-closing, '
             f'proportional overround removal); rows without it are excluded: DEV {payload["n_without_snapshot"]["dev"]}, '
             f'VAL {payload["n_without_snapshot"]["val"]}. All numbers are {LABEL}. Coefficients fitted on DEV rows '
             f'with snapshot odds (n={fits["stack"]["n"]}).', '',
             '| fit | a (log model) | b (log market) | c (H, D, A) |', '|---|---|---|---|',
             *[f'| {label} | {fit["a"]:.6f} | {fit["b"]:.6f} | {", ".join(f"{v:+.6f}" for v in fit["c"])} |'
               for label, fit in fits.items()], '',
             '| rows | model | log-loss | RPS | Brier |', '|---|---|---|---|---|',
             *[f'| {split.upper()} (n={len(rows[split])}) | {label} | {s["logloss"]:.6f} | {s["rps"]:.6f} | '
               f'{s["brier"]:.6f} |' for split in ('dev', 'val') for label, s in table[split].items()], '',
             '"model" is the goals-only incumbent alone on the same rows (descriptive).', '',
             f'Stack minus market-only log-loss on DEV+VAL snapshot rows (n={len(rows["both"])}): {delta.mean():+.6f}; '
             f'99% paired week-block CI [{low:+.6f}, {high:+.6f}] (2000 resamples, seed {SEED}).', '',
             *verdict_lines(checks, verdict),
             '### VAL per league (snapshot rows)', '', harness.markdown_table(per_league, 6), '']
    finish(name, payload, lines, incumbent, None)


# ---------------------------------------------------------------- Phase 4: freeze

def freeze(df, test_index, home_adv):
    missing = [name for name in ORDER if not os.path.exists(path(f'{name}.json'))]
    if missing:
        raise SystemExit(f'Experiments not yet run: {missing}')
    if os.path.exists(path('candidate_p2.json')):
        raise SystemExit('candidate_p2.json already exists; the freeze is final.')
    incumbent = read_json('incumbent.json')
    verdicts = {name: read_json(f'{name}.json')['verdict'] for name in ORDER}
    frames = selection_frames(df, test_index)
    work, both = frames['work'], frames['both']
    model = forecast(work, incumbent['params'], home_adv)
    market, _ = snapshot_market(work, fallback=False)
    rows = both.index[both.index.isin(market.index)]
    actual = outcome_classes(df.loc[rows])
    refits = {label: p2_stack.fit(model.loc[rows].to_numpy(), market.loc[rows].to_numpy(), actual, with_model)
              for label, with_model in (('stack', True), ('market_only', False))}
    goals_accepted = [name for name in ('S0', 'S1') if verdicts[name] == 'ACCEPTED']
    tests = ['T-A'] + (['T-B'] if goals_accepted else []) + (['T-C'] if verdicts['S2'] == 'ACCEPTED' else [])
    payload = dict(
        candidate='P2', frozen_on='2026-10-26', protocol='p2/PREREGISTRATION.md', home_adv=home_adv,
        p1_params=load_p1(),
        goals_only=dict(params=incumbent['params'], shots_w=incumbent['params'].get('shots_w', 0.0),
                        accepted=goals_accepted,
                        note='Overrides of exp_model.DEFAULT_PARAMS plus shots_w, for p2_model.run_filter.'),
        verdicts=verdicts,
        stack=dict(accepted=verdicts['S2'] == 'ACCEPTED', coefficients=refits['stack'],
                   market_only=refits['market_only'], fitted_on='DEV+VAL rows with snapshot odds',
                   use='T-C on F' if verdicts['S2'] == 'ACCEPTED' else 'descriptive Phase 6 only'),
        snapshot=dict(main=list(p2_data.SNAPSHOT_TRIPLE), fresh_without_avg=list(p2_data.SNAPSHOT_FALLBACK),
                      rule='non-closing average triple (DEV missing share 0.34% < 5%); proportional overround removal'),
        shots=dict(columns=list(p2_model.SOT_COLUMNS), min_matches=p2_model.SHOTS_MIN_MATCHES),
        fresh_tests=dict(run=tests, level=FRESH_LEVEL, seed=SEED, n_resamples=N_RESAMPLES,
                         metric='mean per-match log-loss', seasons=p2_data.SCORED_SEASONS),
        sha256='')
    payload['sha256'] = payload_sha(payload)
    write_json('candidate_p2.json', payload)
    print(json.dumps(payload, indent=2))


# ---------------------------------------------------------------- Phase 5: fresh one-shot

def metric_rows(groups, actual, probs, label_key=None):
    records = []
    for group, mask in groups:
        for model, p in probs.items():
            if mask.any():
                records.append({**({label_key: group} if label_key else {}), 'model': model, 'n': int(mask.sum()),
                                **probability_metrics(p[mask], actual[mask])})
    return pd.DataFrame(records)


def fresh_once(home_adv):
    frozen = load_frozen()
    if os.path.exists(path('fresh_once.json')):
        raise SystemExit('The fresh one-shot already ran.')
    fresh = p2_data.load_fresh()
    goals_params, p1 = frozen['goals_only']['params'], frozen['p1_params']
    baseline = exp_run_filter(fresh, DEFAULT_PARAMS, home_adv)
    p1_probs = exp_run_filter(fresh, make_params(**p1), home_adv)
    goals_only = p2_model.run_filter(fresh, goals_params, home_adv)
    p1_check = p2_model.run_filter(fresh, dict(p1, shots_w=0.0), home_adv)
    equal = float(np.abs(p1_check[harness.PROB_COLUMNS].to_numpy() - p1_probs[harness.PROB_COLUMNS].to_numpy()).max())

    scored = p2_data.fresh_scoring_rows(fresh)
    actual = outcome_classes(scored)
    cols = harness.PROB_COLUMNS
    probs = {'Stage 2 baseline': baseline.loc[scored.index, cols].to_numpy(float),
             'P1': p1_probs.loc[scored.index, cols].to_numpy(float)}
    if 'T-B' in frozen['fresh_tests']['run']:
        probs['Goals-only candidate'] = goals_only.loc[scored.index, cols].to_numpy(float)
    loss = {name: harness.row_scores(p, actual)['LogLoss'] for name, p in probs.items()}
    dates = scored['date']
    tests = {}

    def test(name, first, second, first_loss, second_loss, rows_dates):
        delta = first_loss - second_loss
        low, high = week_ci(delta, rows_dates, FRESH_LEVEL)
        tests[name] = dict(comparison=f'{first} minus {second}', n=int(len(delta)), first=float(first_loss.mean()),
                           second=float(second_loss.mean()), mean_delta=float(delta.mean()), ci=[low, high],
                           verdict='PASS' if high < 0 else 'FAIL')
        return delta

    deltas = {'T-A': test('T-A', 'P1', 'Stage 2 baseline', loss['P1'], loss['Stage 2 baseline'], dates)}
    if 'T-B' in frozen['fresh_tests']['run']:
        deltas['T-B'] = test('T-B', 'Goals-only candidate', 'P1', loss['Goals-only candidate'], loss['P1'], dates)

    market, snapshot_cols = snapshot_market(scored, fallback=True)
    has = scored.index.isin(market.index)
    model_for_stack = goals_only.loc[scored.index, cols]
    stack = stack_probs(frozen['stack']['coefficients'], model_for_stack, market)
    market_only = stack_probs(frozen['stack']['market_only'], model_for_stack, market)
    if 'T-C' in frozen['fresh_tests']['run']:
        stack_loss = harness.row_scores(stack.to_numpy(), actual[has])['LogLoss']
        market_loss = harness.row_scores(market_only.to_numpy(), actual[has])['LogLoss']
        deltas['T-C'] = test('T-C', 'Stack', 'Market-only', stack_loss, market_loss, dates[has])

    lines = [f'# {FRESH_LABEL}', '', f'**{FRESH_LABEL}.** Pre-registered in `p2/PREREGISTRATION.md`; candidates frozen in '
             f'`results/p2/candidate_p2.json` (sha256 {frozen["sha256"]}). Rows: every F match of 2015-2016 to '
             f'2018-2019 (n={len(scored)}); 2014-2015 is burn-in. home_adv {home_adv:.6f} (main-data value). '
             f'CIs: paired week-block bootstrap, 2000 resamples, seed {SEED}, level 1 - 0.05/3 (98.3%). A test passes '
             'only if the upper bound is below 0.', '',
             f'Check (forecasts only): p2_model with shots_w = 0 vs exp_model P1 on all {len(fresh)} F rows, max abs '
             f'probability difference {equal:.1e}.', '',
             '## Primary tests', '', '| test | comparison | n | first | second | mean diff | 98.3% CI | verdict |',
             '|---|---|---|---|---|---|---|---|',
             *[f'| {name} | {t["comparison"]} | {t["n"]} | {t["first"]:.6f} | {t["second"]:.6f} | '
               f'{t["mean_delta"]:+.6f} | [{t["ci"][0]:+.6f}, {t["ci"][1]:+.6f}] | **{t["verdict"]}** |'
               for name, t in tests.items()],
             *[f'- {name}: not run (pre-registered condition not met: '
               f'{"S0 and S1 rejected" if name == "T-B" else "S2 rejected"}).'
               for name in ('T-B', 'T-C') if name not in tests], '']

    per_group = {}
    for key in ('season', 'competition'):
        group_rows = []
        for group, ids in scored.groupby(key).groups.items():
            mask = scored.index.isin(ids)
            for name, delta in deltas.items():
                if name == 'T-C':
                    sub = mask[has]
                    rows_dates, d = dates[has][sub], delta[sub]
                else:
                    rows_dates, d = dates[mask], delta[mask]
                if len(d):
                    low, high = week_ci(d, rows_dates, FRESH_LEVEL)
                    group_rows.append({key: group, 'test': name, 'n': int(len(d)), 'mean diff': float(d.mean()),
                                       'CI low': low, 'CI high': high})
        per_group[key] = pd.DataFrame(group_rows)
        lines += [f'### Test differences per {key} (descriptive; 98.3% CIs, no per-group verdict)', '',
                  harness.markdown_table(per_group[key], 6), '']

    lines += ['## Secondary metrics (descriptive)', '', '### All scored F rows', '',
              harness.markdown_table(metric_rows([('all', np.ones(len(scored), bool))], actual, probs), 6), '']
    for key in ('season', 'competition'):
        groups = [(group, scored.index.isin(ids)) for group, ids in scored.groupby(key).groups.items()]
        lines += [f'### Per {key}', '', harness.markdown_table(metric_rows(groups, actual, probs, key), 6), '']

    closing_rows, closing_label = None, None
    for triple, label in p2_data.CLOSING_CHOICES:
        mask = p2_data.valid_triple(scored, triple).to_numpy()
        if mask.any():
            closing_rows, closing_label, closing_triple = mask, label, triple
            break
    snap_probs = {name: p[has] for name, p in probs.items()}
    snap_probs.update({'Stack': stack.to_numpy(), 'Market-only (snapshot)': market_only.to_numpy()})
    lines += [f'### Rows with snapshot odds (n={int(has.sum())}; columns {sorted(set(snapshot_cols[has]))})', '',
              f'Stack and market-only use the frozen DEV+VAL coefficients ({frozen["stack"]["use"]}).', '',
              harness.markdown_table(metric_rows([('snapshot rows', np.ones(int(has.sum()), bool))], actual[has],
                                                 snap_probs), 6), '']
    if closing_rows is not None:
        odds = scored.loc[closing_rows, list(closing_triple)].apply(pd.to_numeric, errors='coerce').to_numpy()
        closing_probs = {name: p[closing_rows] for name, p in probs.items()}
        closing_probs[f'{closing_label} market'] = p2_stack.market_probs(odds)
        frame = metric_rows([('closing rows', np.ones(int(closing_rows.sum()), bool))], actual[closing_rows],
                            closing_probs)
        lines += [f'### Gap to the {closing_label} market ({"/".join(closing_triple)}; rows with it, '
                  f'n={int(closing_rows.sum())})', '',
                  f'Bookmaker: {closing_label}. Closing odds are later than any T-60 forecast: benchmark only. Not '
                  'comparable with the TEST-era closing-average figures.', '', harness.markdown_table(frame, 6), '']
    write_text('fresh_once.md', '\n'.join(lines))
    write_json('fresh_once.json', dict(label=FRESH_LABEL, frozen_sha256=frozen['sha256'], n_scored=len(scored),
                                       n_snapshot=int(has.sum()), p1_equality_max_diff=equal, tests=tests,
                                       per_season=per_group['season'].to_dict(orient='records'),
                                       per_league=per_group['competition'].to_dict(orient='records')))
    print('\n'.join(lines[:30]))


# ---------------------------------------------------------------- Phase 6: descriptive TEST look

def test_look(df, test_index, home_adv):
    frozen = load_frozen()
    if not os.path.exists(path('fresh_once.md')):
        raise SystemExit('Phase 5 must be written first.')
    if os.path.exists(path('test_descriptive.md')):
        raise SystemExit('The descriptive TEST look already ran.')
    full = df[COLUMNS + list(p2_data.SNAPSHOT_TRIPLE)]
    goals_params, p1 = frozen['goals_only']['params'], frozen['p1_params']
    cols = harness.PROB_COLUMNS
    test = df.loc[test_index]
    actual = outcome_classes(test)
    goals_only = p2_model.run_filter(full, goals_params, home_adv)
    probs = {'Stage 2 baseline': exp_run_filter(full, DEFAULT_PARAMS, home_adv).loc[test_index, cols].to_numpy(float),
             'P1': exp_run_filter(full, make_params(**p1), home_adv).loc[test_index, cols].to_numpy(float),
             'Goals-only candidate': goals_only.loc[test_index, cols].to_numpy(float)}
    market, _ = snapshot_market(test, fallback=False)
    has = test.index.isin(market.index)
    model_for_stack = goals_only.loc[test_index, cols]
    snap = {name: p[has] for name, p in probs.items()}
    snap['Stack'] = stack_probs(frozen['stack']['coefficients'], model_for_stack, market).to_numpy()
    snap['Market-only (snapshot)'] = stack_probs(frozen['stack']['market_only'], model_for_stack, market).to_numpy()
    closing, closing_mask = harness.market_probs(test)
    both = closing_mask & has
    full_rows = {name: np.full((len(test), 3), np.nan) for name in ('Stack', 'Market-only (snapshot)')}
    for name in full_rows:
        full_rows[name][has] = snap[name]
    closing_probs = {name: p[both] for name, p in probs.items()}
    closing_probs.update({name: full_rows[name][both] for name in full_rows})
    closing_probs['Closing market (average)'] = closing[both]
    tables = [('All TEST rows', np.ones(len(test), bool), probs),
              ('TEST rows with snapshot odds', has, snap),
              ('TEST rows with snapshot and closing odds', both, closing_probs)]
    lines = [f'# P2 frozen candidates on TEST rows: {TEST_LABEL}', '',
             f'**{TEST_LABEL}.** TEST_INDEX ({len(test)} rows) was examined in Stages 1-5 and in the P1 test; this '
             'look comes after the fresh scoring (`results/p2/fresh_once.md`) and changes nothing. Helpers: '
             '`exp_harness.row_scores`/`market_probs`, `metrics.probability_metrics`. Stack and market-only use the '
             f'frozen DEV+VAL coefficients ({frozen["stack"]["use"]}).', '']
    records = {}
    for title, mask, table_probs in tables:
        frame = metric_rows([(title, np.ones(int(mask.sum()), bool))], actual[mask], table_probs)
        records[title] = frame.to_dict(orient='records')
        lines += [f'## {title} (n={int(mask.sum())}). {TEST_LABEL}', '', harness.markdown_table(frame, 6), '']
    write_text('test_descriptive.md', '\n'.join(lines))
    write_json('test_descriptive.json', dict(label=TEST_LABEL, frozen_sha256=frozen['sha256'], tables=records))
    print('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--fetch', action='store_true')
    group.add_argument('--check', action='store_true')
    group.add_argument('--select', choices=ORDER)
    group.add_argument('--freeze', action='store_true')
    group.add_argument('--fresh', action='store_true')
    group.add_argument('--test-look', action='store_true')
    args = parser.parse_args()
    if args.fetch:
        fetch()
        return
    df, _, test_index, home_adv = load_data()
    if args.check:
        check(df, home_adv)
    elif args.select == 'S2':
        run_stack_experiment(df, test_index, home_adv)
    elif args.select:
        run_goals_experiment(args.select, df, test_index, home_adv)
    elif args.freeze:
        freeze(df, test_index, home_adv)
    elif args.fresh:
        fresh_once(home_adv)
    else:
        test_look(df, test_index, home_adv)


if __name__ == '__main__':
    main()
