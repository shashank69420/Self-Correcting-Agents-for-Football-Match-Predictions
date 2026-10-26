"""P2: fresh-season replication of P1 and three pre-registered improvements (p2/PREREGISTRATION.md).

python -X utf8 run_p2.py --fetch     Phase 2: fetch 2014-2019, write results/p2/data_audit.md (counts only)
"""
import argparse
import os

import pandas as pd

import p2_data

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(PROJECT_DIR, 'results', 'p2')


def write_text(name, text):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, name), 'w', encoding='utf-8') as handle:
        handle.write(text)


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


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--fetch', action='store_true')
    args = parser.parse_args()
    if args.fetch:
        fetch()


if __name__ == '__main__':
    main()
