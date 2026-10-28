"""Build site/data.json for the project website from committed result files.

Copies values only: it never fits, scores or re-runs a model and never fetches anything. Headline figures are taken
from results/claims.json by claim id; per-match and per-team values are copied from their result files.

Usage: python -X utf8 site/build_data.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'site', 'data.json')

INPUTS = dict(
    readme='README.md',
    findings='results/FINDINGS.md',
    primary_md='results/live2627/primary.md',
    primary='results/live2627/primary.json',
    manifest='results/live2627/manifest_20261026.json',
    ratings='results/fan/ratings.json',
    constants='results/fan/model_constants.json',
    samples='results/fan/sample_forecasts.json',
    calibration='results/fan/markets_calibration.json',
    pp_decision='results/pp/pp_decision.md',
    claims='results/claims.json',
    forward='forward/predictions.jsonl',
)

# Headline figures shown on the site, by claim id (results/claims.json).
CLAIM_IDS = [
    # Section 2: baselines
    'c019', 'c020', 'c023',
    # Section 3: surprise mechanism, validation log-loss by sensitivity
    'c032', 'c040', 'c042', 'c044',
    # Section 4: Gate B
    'c047', 'c048', 'c049', 'c050', 'c051', 'c052', 'c060', 'c061', 'c062',
    # Section 6: one-shot TEST
    'c008', 'c122', 'c123', 'c124', 'c125', 'c126',
    # Section 9: P2 selection and fresh seasons
    'p2_003', 'p2_004', 'p2_014', 'p2_023', 'p2_024', 'p2_026', 'p2_027', 'p2_028', 'p2_029', 'p2_032', 'p2_033',
    'p2_034',
    # Section 10: 2026-27
    'l10_001', 'l10_002', 'l10_003', 'l10_004', 'l10_005', 'l10_006', 'l10_007', 'l10_008', 'l10_009', 'l10_010',
    'l10_011', 'l10_012', 'l10_013', 'l10_014', 'l10_015', 'l10_020', 'l10_021', 'l10_022', 'l10_023', 'l10_024',
    'l10_025',
    # Section 12: posterior predictive
    'pp_007', 'pp_008', 'pp_009', 'pp_010', 'pp_011', 'pp_012', 'pp_013',
]

MODEL_KEYS = ('M0', 'M2', 'M4')  # Stage 2 baseline, P2 goals-only (final), closing average (per primary.md)


def path(key):
    return os.path.join(ROOT, INPUTS[key])


def load_json(key):
    with open(path(key), encoding='utf-8') as handle:
        return json.load(handle)


def main():
    missing = [rel for rel in INPUTS.values() if not os.path.isfile(os.path.join(ROOT, rel))]
    assert not missing, f'missing inputs: {missing}'

    claims = {c['id']: c['value'] for c in load_json('claims')['claims']}
    absent = [cid for cid in CLAIM_IDS if cid not in claims]
    assert not absent, f'claim ids not in results/claims.json: {absent}'

    primary = load_json('primary')
    manifest = load_json('manifest')
    ratings = load_json('ratings')
    constants = load_json('constants')
    samples = load_json('samples')

    rows = primary['scored_rows']
    assert len(rows) == primary['counts']['test_set'], 'scored_rows does not match the test-set count'
    matches = [dict(league=r['league'], datetime=r['datetime'], home=r['home'], away=r['away'],
                    goals_home=r['goals_home'], goals_away=r['goals_away'], newcomer=r['newcomer'],
                    **{k: r[k] for k in MODEL_KEYS}) for r in rows]

    with open(path('forward'), encoding='utf-8') as handle:
        logged = [json.loads(line) for line in handle if line.strip()]
    forward = [dict(league=r['league'], home=r['home'], away=r['away'], kickoff_utc=r['kickoff_utc'],
                    logged_at_utc=r['logged_at_utc'],
                    base=[r['base_home'], r['base_draw'], r['base_away']],
                    p1=[r['p1_home'], r['p1_draw'], r['p1_away']],
                    scored='result' in r or 'goals_home' in r) for r in logged]

    data = dict(
        claims={cid: claims[cid] for cid in CLAIM_IDS},
        season=dict(
            label=primary['label'], wording=primary['wording'], snapshot_date=primary['snapshot_date'],
            preregistration_commit=primary['preregistration_commit'],
            manifest_preregistration=manifest['preregistration'],
            fetched_at_utc=manifest['fetched_at_utc'], earliest_date=manifest['earliest_date'],
            latest_date=manifest['latest_date'], rows_sha256=manifest['rows_sha256'],
            code_commit=primary['code_commit'], p2_frozen_sha256=primary['p2_frozen_sha256'],
            matches=matches),
        ratings=dict(label=ratings['label'], bar_label=ratings['bar_label'],
                     defence_bar_note=ratings['defence_bar_note'], interval=ratings['interval'],
                     lower_defence_is_better=ratings['lower_defence_is_better'], excluded=ratings['excluded'],
                     leagues=ratings['leagues']),
        constants=dict(home_adv=constants['home_adv'], rho=constants['rho'], rate_bounds=constants['rate_bounds'],
                       clip_rates=constants['clip_rates'], grid=constants['grid'], markets=constants['markets'],
                       snapshot_date=constants['provenance']['snapshot_date']),
        samples=samples['samples'],
        forward=forward,
    )
    assert data['constants']['rho'] == samples['rho']

    with open(OUT, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, separators=(',', ':'))

    teams = sum(len(league['teams']) for league in ratings['leagues'])
    print(f'claims: {len(data["claims"])}; 2026-27 matches: {len(matches)}; leagues rated: {len(ratings["leagues"])}, '
          f'teams: {teams}; parity samples: {len(data["samples"])}; forward log rows: {len(forward)} '
          f'(scored in log: {sum(f["scored"] for f in forward)})')
    print(f'wrote {os.path.relpath(OUT, ROOT)} ({os.path.getsize(OUT) // 1024} KiB)')


if __name__ == '__main__':
    main()
