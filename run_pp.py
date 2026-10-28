"""PP v2 (pp/PREREGISTRATION_v2.md): outcome-free node selection, then one DEV/VAL evaluation.

python -X utf8 run_pp.py --select-nodes   writes results/pp/pp_nodes.json (forecasts compared with forecasts only)
python -X utf8 run_pp.py --evaluate       writes results/pp/pp_dev_val.json and results/pp/pp_decision.md, once

Both refuse to overwrite their outputs. The evaluation reuses the P2 selection harness: run_p2.selection_frames,
run_p2.scores, run_p2.row_loss, run_p2.week_ci at run_p2.SELECT_LEVEL and exp_harness.accept.
"""
import argparse
import hashlib
import json
import os
import subprocess
import time

import numpy as np

import exp_harness as harness
import p2_model
import pp_model
import run_p2
from run_experiments import load_data

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(PROJECT_DIR, 'results', 'pp')
PROTOCOL = 'pp/PREREGISTRATION_v2.md'
LABEL = 'v2, revised after a failed numerical check'
PLUG_IN_COLUMNS = ['pred_home_win', 'pred_draw', 'pred_away_win', 'lambda_home', 'mu_away', 'shots_weight']
HOME_ADV_TOLERANCE = 1e-12


def path(name):
    return os.path.join(RESULTS_DIR, name)


def write_new(name, text):
    if os.path.exists(path(name)):
        raise SystemExit(f'results/pp/{name} exists; this step runs once.')
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(path(name), 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)


def committed_sha256(relative):
    """sha256 of the committed blob, as recorded in DECISIONS.md."""
    blob = subprocess.run(['git', 'show', f'HEAD:{relative}'], cwd=PROJECT_DIR, capture_output=True, check=True).stdout
    return hashlib.sha256(blob).hexdigest()


def load_work():
    """Selection frames (non-TEST only), TEST_INDEX, frozen goals-only params and the frozen home_adv."""
    df, _, test_index, home_adv = load_data()
    frozen = run_p2.load_frozen()
    if abs(home_adv - frozen['home_adv']) > HOME_ADV_TOLERANCE:
        raise SystemExit(f'home_adv {home_adv!r} differs from the frozen {frozen["home_adv"]!r}')
    return run_p2.selection_frames(df, test_index), test_index, frozen['goals_only']['params'], frozen['home_adv']


def select_nodes():
    if os.path.exists(path('pp_nodes.json')):
        raise SystemExit('results/pp/pp_nodes.json exists; N* is selected once.')
    started = time.time()
    frames, _, params, home_adv = load_work()
    model = p2_model.split_params(params)[0]
    bounds = model['rate_bounds'] if model['clip_rates'] else None
    # The states do not depend on the node count; the smallest ladder value is the cheapest run.
    output = pp_model.run_filter(frames['work'], params, home_adv, pp_model.LADDER[0])
    rows = pp_model.selection_rows(output)
    errors = pp_model.ladder_errors(rows, model['rho'], bounds)
    n_star = pp_model.select_nodes(errors)
    payload = dict(label=LABEL, protocol=PROTOCOL, protocol_sha256=committed_sha256(PROTOCOL), outcomes_used=False,
                   reference_nodes=pp_model.REFERENCE_NODES, ladder=list(pp_model.LADDER),
                   tolerance=pp_model.NODE_TOLERANCE, seed=pp_model.SELECTION_SEED, n_rows=len(rows),
                   n_work_rows=len(output), max_error={str(n): e for n, e in errors.items()}, n_star=n_star,
                   n_star_max_error=errors[n_star], seconds=round(time.time() - started, 1))
    write_new('pp_nodes.json', json.dumps(payload, indent=2) + '\n')
    print(json.dumps({k: payload[k] for k in ('n_star', 'n_star_max_error', 'max_error', 'n_rows')}, indent=1))


def evaluate():
    if os.path.exists(path('pp_dev_val.json')):
        raise SystemExit('results/pp/pp_dev_val.json exists; the evaluation runs once.')
    if not os.path.exists(path('pp_nodes.json')):
        raise SystemExit('results/pp/pp_nodes.json is missing; select N* first.')
    with open(path('pp_nodes.json'), encoding='utf-8') as handle:
        nodes = json.load(handle)['n_star']
    started = time.time()
    frames, test_index, params, home_adv = load_work()
    work, dev, val, both = frames['work'], frames['dev'], frames['val'], frames['both']
    base = p2_model.run_filter(work, params, home_adv)
    output = pp_model.run_filter(work, params, home_adv, nodes)
    gap = float(np.abs(output[PLUG_IN_COLUMNS].to_numpy() - base[PLUG_IN_COLUMNS].to_numpy()).max())
    if gap > 1e-12:
        raise SystemExit(f'pp_model plug-in forecast differs from p2_model by {gap}')
    probs = dict(baseline=base[harness.PROB_COLUMNS],
                 pp=output[pp_model.PP_COLUMNS].set_axis(harness.PROB_COLUMNS, axis=1))
    splits = dict(dev=dev, val=val, pooled=both)
    table = {name: {split: run_p2.scores(frame, test_index, p.loc[frame.index]) for split, frame in splits.items()}
             for name, p in probs.items()}
    differences = {split: {metric: table['pp'][split][metric] - table['baseline'][split][metric]
                           for metric in ('logloss', 'rps', 'brier')} for split in splits}

    delta = (run_p2.row_loss(both, test_index, probs['pp'].loc[both.index])
             - run_p2.row_loss(both, test_index, probs['baseline'].loc[both.index]))
    low, high = run_p2.week_ci(delta, both['date'], run_p2.SELECT_LEVEL)
    accepted, checks = harness.accept(table['baseline']['dev']['logloss'], table['pp']['dev']['logloss'],
                                      table['baseline']['val']['logloss'], table['pp']['val']['logloss'], high)
    rps = {name: harness.row_scores(*harness.scored(both, test_index, p.loc[both.index]))['RPS']
           for name, p in probs.items()}
    rps_low, rps_high = run_p2.week_ci(rps['pp'] - rps['baseline'], both['date'], run_p2.SELECT_LEVEL)
    per_league = harness.grouped_metrics(val, test_index, {name: p.loc[val.index].to_numpy()
                                                           for name, p in probs.items()}, 'competition')
    verdict = 'ACCEPTED' if accepted else 'REJECTED'
    payload = dict(label=LABEL, selection_label=harness.LABEL, protocol=PROTOCOL,
                   protocol_sha256=committed_sha256(PROTOCOL), nodes=nodes, verdict=verdict,
                   checks={k: bool(v) for k, v in checks.items()}, table=table, differences=differences,
                   n_dev=len(dev), n_val=len(val), n_pooled=len(both), mean_delta_logloss=float(delta.mean()),
                   ci99_logloss=[low, high], ci99_rps=[rps_low, rps_high], seed=run_p2.SEED,
                   n_resamples=run_p2.N_RESAMPLES, plug_in_gap=gap,
                   per_league_val=per_league.to_dict(orient='records'), seconds=round(time.time() - started, 1))
    write_new('pp_dev_val.json', json.dumps(payload, indent=2) + '\n')
    write_new('pp_decision.md', decision_text(payload, per_league))
    print(decision_text(payload, per_league)[:2500])


def decision_text(p, per_league):
    def row(name, split):
        s = p['table'][name][split]
        return f'| {name} | {split} | {s["logloss"]:.6f} | {s["rps"]:.6f} | {s["brier"]:.6f} |'

    lines = [f'# PP decision ({p["label"]})', '',
             f'{p["selection_label"]}. Protocol: `{p["protocol"]}` (sha256 {p["protocol_sha256"]}). '
             f'PP uses N* = {p["nodes"]} Gauss-Hermite nodes (`results/pp/pp_nodes.json`). Baseline: the frozen P2 '
             'goals-only candidate. Only the forecast step differs.', '',
             '| model | split | log-loss | RPS | Brier |', '|---|---|---|---|---|',
             *[row(name, split) for split in ('dev', 'val', 'pooled') for name in ('baseline', 'pp')], '',
             f'Rows: DEV {p["n_dev"]}, VAL {p["n_val"]}, DEV+VAL {p["n_pooled"]}.', '',
             '| split | log-loss PP minus baseline | RPS PP minus baseline | Brier PP minus baseline |',
             '|---|---|---|---|',
             *[f'| {split} | {d["logloss"]:+.6f} | {d["rps"]:+.6f} | {d["brier"]:+.6f} |'
               for split, d in p['differences'].items()], '',
             f'Decisive: 99% paired week-block CI of the per-row log-loss difference on DEV+VAL '
             f'({p["n_resamples"]} resamples, seed {p["seed"]}): [{p["ci99_logloss"][0]:+.6f}, '
             f'{p["ci99_logloss"][1]:+.6f}].', '',
             f'Reported, not decisive: 99% CI of the per-row RPS difference: [{p["ci99_rps"][0]:+.6f}, '
             f'{p["ci99_rps"][1]:+.6f}].', '',
             *[f'- {key}: {"yes" if value else "NO"}' for key, value in p['checks'].items()], '',
             f'Verdict: **{p["verdict"]}**.', '',
             '## VAL per league (descriptive, no per-league verdict)', '',
             harness.markdown_table(per_league[['competition', 'model', 'n', 'LogLoss', 'RPS', 'Brier']], 6), '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--select-nodes', action='store_true')
    group.add_argument('--evaluate', action='store_true')
    args = parser.parse_args()
    if args.select_nodes:
        select_nodes()
    else:
        evaluate()


if __name__ == '__main__':
    main()
