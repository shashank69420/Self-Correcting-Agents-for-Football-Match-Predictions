"""Network-free tests for fan_features.py (synthetic data, committed result files, and the local cache where noted).

Run: python -X utf8 -m pytest -q tests/test_fan.py
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

import numpy as np
import pandas as pd
from scipy.stats import poisson

import exp_model
import fan_features as fan
import p2_model

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import verify_claims  # noqa: E402

WORDING = ('Parameters were fixed before 2026-27 data was fetched. Forecasts were recomputed after the matches were '
           'played and are not timestamped before kickoff.')
BASE_COMMIT = '695d4e1ba610bc6f2e19d88d672d2421ad7fb786'  # the last commit before the ratings-check correction
# sha256 of the LF-normalised committed bytes at BASE_COMMIT; the files are hashed as opaque bytes, never parsed.
METRIC_FILES = {
    'results/fan/markets_calibration.json': '60e7e53276369e95f35987dc434cfde84c3871cdc599948712e8967b4bc00aa8',
    'results/live2627/primary.json': '67873ed4f3b641d690897d2e78bfcc94c6712af380b136c2b9aaf197a67577e6',
    'results/p2/S0.json': 'a2899d5ee9bfef6f98303069c399be41e3df2e470e6796770f6957b36d0e9463',
    'results/p2/S1.json': 'ba872df98aa742838c101f3399439f6dfcf33c52c01a535abce76e171842b110',
    'results/p2/S2.json': 'e441a646309f36b1a75dfaef7efaaf57d593a084c77954fdb356193bba648cb9',
}


def path(*parts):
    return os.path.join(ROOT, *parts)


def read_text(*parts):
    with open(path(*parts), encoding='utf-8') as handle:
        return handle.read()


def read_json(*parts):
    return json.loads(read_text(*parts))


def sha256_lf(data):
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def p2_params():
    return read_json('results', 'p2', 'candidate_p2.json')['goals_only']['params']


def synthetic_frame(seed=3, teams=6, rounds=4):
    """A small double-round-robin league with scores and no shots columns."""
    rng = np.random.default_rng(seed)
    names = [f'T{i}' for i in range(teams)]
    rows = []
    for number in range(rounds):
        for home, away in [(a, b) for a in names for b in names if a != b][number::rounds]:
            rows.append(dict(competition='L', season='2020-2021', date=pd.Timestamp('2020-08-01') +
                             pd.Timedelta(days=7 * number), team_home=home, team_away=away,
                             goals_home=int(rng.poisson(1.5)), goals_away=int(rng.poisson(1.1))))
    return pd.DataFrame(rows).sort_values('date', kind='stable').reset_index(drop=True)


def state(attack_mean, attack_var, defence_mean, defence_var):
    return SimpleNamespace(attack_mean=attack_mean, attack_var=attack_var, defence_mean=defence_mean,
                           defence_var=defence_var)


def synthetic_ratings(flagged=()):
    teams = ['A', 'B', 'C', 'D', 'E']
    rng = np.random.default_rng(5)
    states = {t: state(rng.normal(0, 0.3), 0.05 + 0.01 * i, rng.normal(0, 0.3), 0.06 + 0.01 * i)
              for i, t in enumerate(teams)}
    live = pd.DataFrame(dict(competition='L', team_home=['A', 'B', 'C', 'D', 'E'], team_away=['B', 'C', 'D', 'E', 'A']))
    history = pd.DataFrame(dict(team_home=['A', 'B', 'C', 'D'], team_away=['B', 'C', 'D', 'A']))
    return fan.league_ratings(states, history, live, list(flagged)), states


class GridTests(unittest.TestCase):
    def test_mass_check_raises_when_the_grid_loses_mass(self):
        with self.assertRaises(ValueError):
            fan.score_grid(40.0, 1.0, -0.04)
        self.assertAlmostEqual(fan.score_grid(1.4, 1.1, -0.04).sum(), 1.0, places=12)

    def test_top_scorelines_are_sorted_and_bounded(self):
        top = fan.top_scorelines(fan.score_grid(1.6, 1.0, -0.04))
        probabilities = [p for _, _, p in top]
        self.assertEqual(len(top), fan.TOP_K)
        self.assertEqual(probabilities, sorted(probabilities, reverse=True))
        self.assertLessEqual(sum(probabilities), 1.0)
        self.assertEqual(len({(h, a) for h, a, _ in top}), fan.TOP_K)

    def test_markets_and_their_complements_sum_to_one(self):
        m = fan.markets(fan.score_grid(1.7, 1.2, -0.04))
        self.assertAlmostEqual(m['over_2_5'] + m['under_2_5'], 1.0, places=12)
        self.assertAlmostEqual(m['btts'] + m['btts_no'], 1.0, places=12)
        self.assertAlmostEqual(m['home'] + m['draw'] + m['away'], 1.0, places=12)

    def test_rho_zero_factorises_with_closed_form_markets(self):
        lam, mu = 1.4, 1.1
        grid = fan.score_grid(lam, mu, 0.0)
        goals = np.arange(fan.MARKET_GOALS + 1)
        outer = np.outer(poisson.pmf(goals, lam), poisson.pmf(goals, mu))
        self.assertLess(np.abs(grid - outer / outer.sum()).max(), 1e-15)
        self.assertAlmostEqual(fan.p_btts(grid), (1 - np.exp(-lam)) * (1 - np.exp(-mu)), places=12)
        self.assertAlmostEqual(fan.p_over(grid), 1 - poisson.cdf(2, lam + mu), places=12)
        xg_home, xg_away = fan.expected_goals(grid)
        self.assertAlmostEqual(xg_home, lam, places=9)
        self.assertAlmostEqual(xg_away, mu, places=9)

    def test_1x2_equals_the_models_function_where_ten_goals_lose_nothing(self):
        lam, mu, rho = 0.3, 0.25, -0.04
        ours = np.array(fan.outcome_probs(fan.score_grid(lam, mu, rho)))
        theirs = np.array(exp_model.dixon_coles_probs(lam, mu, rho))
        self.assertLess(np.abs(ours - theirs).max(), 1e-12)

    def test_reimplementation_equals_the_models_function_at_its_own_size(self):
        for lam, mu in ((1.5, 1.1), (0.9, 2.3), (2.6, 0.6)):
            ours = np.array(fan.outcome_probs(fan.score_grid(lam, mu, -0.04, max_goals=fan.MODEL_GOALS, min_mass=0.9)))
            theirs = np.array(exp_model.dixon_coles_probs(lam, mu, -0.04))
            self.assertLess(np.abs(ours - theirs).max(), 1e-12)


class ForecastTests(unittest.TestCase):
    def test_a_rows_forecast_is_unchanged_if_later_rows_are_removed(self):
        frame, params = synthetic_frame(), p2_params()
        full = p2_model.run_filter(frame, params, 0.2)
        cut = len(frame) // 2
        part = p2_model.run_filter(frame.iloc[:cut], params, 0.2)
        pd.testing.assert_frame_equal(full.iloc[:cut], part)

    def test_final_states_wrapping_does_not_change_the_forecasts(self):
        frame, params = synthetic_frame(), p2_params()
        states, forecasts = fan.final_states(frame, params, 0.2)
        pd.testing.assert_frame_equal(forecasts, p2_model.run_filter(frame, params, 0.2))
        self.assertEqual(set(states), set(frame['team_home']) | set(frame['team_away']))

    def test_climatology_uses_no_scored_row(self):
        dates = pd.to_datetime(['2019-09-01', '2019-10-01', '2020-06-01', '2020-09-01', '2023-09-01'])
        both = pd.DataFrame(dict(frame='H', is_test=False, date=dates, goals_home=[2, 0, 3, 1, 2],
                                 goals_away=[1, 0, 1, 1, 2]))
        base = fan.climatology_rates(both, pd.Index([3, 4]))
        self.assertEqual(base['n'], 3)
        changed = both.copy()
        changed.loc[[3, 4], ['goals_home', 'goals_away']] = 9
        self.assertEqual(fan.climatology_rates(changed, pd.Index([3, 4])), base)
        with self.assertRaises(AssertionError):
            fan.climatology_rates(both, pd.Index([1]))
        flagged = both.assign(is_test=[False, True, False, False, False])
        with self.assertRaises(AssertionError):
            fan.climatology_rates(flagged, pd.Index([3, 4]))

    def test_binary_block_skill_and_reliability_counts(self):
        p, y = np.array([0.2, 0.6, 0.6, 0.9]), np.array([0.0, 1.0, 0.0, 1.0])
        block = fan.binary_block(p, y, 0.5)
        self.assertAlmostEqual(block['brier'], np.mean((p - y) ** 2), places=12)
        self.assertAlmostEqual(block['brier_skill'], 1 - block['brier'] / 0.25, places=12)
        self.assertEqual(sum(row['n'] for row in block['reliability']), 4)


class RatingsTests(unittest.TestCase):
    def test_centred_log_factors_sum_to_zero_within_a_league(self):
        leagues, _ = synthetic_ratings()
        for side in ('attack', 'defence'):
            self.assertLess(abs(np.sum(np.log([t[f'{side}_factor'] for t in leagues[0]['teams']]))), 1e-12)

    def test_interval_is_symmetric_on_the_log_scale_and_ordered(self):
        leagues, _ = synthetic_ratings()
        for team in leagues[0]['teams']:
            for side in ('attack', 'defence'):
                low, mid, high = (team[f'{side}_{k}'] for k in ('low', 'factor', 'high'))
                self.assertLess(low, mid)
                self.assertLess(mid, high)
                self.assertAlmostEqual(np.log(high) - np.log(mid), np.log(mid) - np.log(low), places=12)
                self.assertAlmostEqual(np.log(high) - np.log(mid), team[f'{side}_sd'], places=12)

    def test_an_alias_flagged_team_is_excluded_and_does_not_set_the_centre(self):
        flagged = [dict(league='L', team='E', reason='alias', alias_of='X')]
        leagues, states = synthetic_ratings(flagged)
        names = [t['team'] for t in leagues[0]['teams']]
        self.assertNotIn('E', names)
        self.assertEqual(len(names), 4)
        self.assertAlmostEqual(leagues[0]['centre']['attack'], np.mean([states[t].attack_mean for t in 'ABCD']), places=12)

    def test_newcomers_ranks_and_labels(self):
        leagues, _ = synthetic_ratings()
        teams = leagues[0]['teams']
        self.assertEqual([t['team'] for t in teams if t['newcomer']], ['E'])
        best_defence = min(teams, key=lambda t: t['defence_factor'])
        self.assertEqual(best_defence['rank_defence'], 1)
        self.assertEqual([t['rank_overall'] for t in teams], sorted(t['rank_overall'] for t in teams))
        self.assertTrue(leagues[0]['lower_defence_is_better'])
        self.assertEqual(leagues[0]['defence_bar_note'], fan.DEFENCE_BAR_NOTE)
        self.assertTrue(all(t['bar_label'] == fan.BAR_LABEL for t in teams))

    def test_ratings_round_trip_through_the_loader(self):
        leagues, _ = synthetic_ratings()
        payload = dict(leagues=leagues, bar_label=fan.BAR_LABEL)
        with tempfile.TemporaryDirectory() as root:
            fan.write_json('ratings.json', payload, root)
            loaded = fan.load_ratings(os.path.join(root, fan.RESULTS, 'ratings.json'))
        self.assertEqual(loaded, json.loads(json.dumps(payload)))
        with self.assertRaises(ValueError):
            fan.load_ratings(os.path.join(ROOT, 'results', 'claims.json'))

    def test_reading_sentence_order_and_n(self):
        display = dict(spearman_defence='+0.456', spearman_attack='-0.396')
        text = fan.reading_sentence(-0.396, 0.456, 139, display)
        self.assertLess(text.index('did not hold'), text.index('defence sd rises'))
        self.assertLess(text.index('defence sd rises'), text.index('attack sd falls'))
        self.assertLess(text.index('attack sd falls'), text.index('n = 139 established teams'))
        self.assertIn('held:', fan.reading_sentence(-0.2, -0.3, 10, display))


class CommittedFileTests(unittest.TestCase):
    def test_committed_forecast_metrics_are_byte_identical_to_the_base_commit(self):
        for name, pin in METRIC_FILES.items():
            with open(path(*name.split('/')), 'rb') as handle:
                self.assertEqual(sha256_lf(handle.read()), pin, f'{name} differs from {BASE_COMMIT[:7]}')
            shown = subprocess.run(['git', 'show', f'{BASE_COMMIT}:{name}'], cwd=ROOT, capture_output=True)
            if shown.returncode == 0:
                self.assertEqual(sha256_lf(shown.stdout), pin, f'{name}: the pin does not match the base commit')

    def test_regenerating_the_committed_markets_changes_nothing(self):
        committed = read_json('results', 'fan', 'markets_calibration.json')
        with tempfile.TemporaryDirectory() as root:
            fan.write_json('markets_calibration.json', committed, root)
            before = open(os.path.join(root, fan.RESULTS, 'markets_calibration.json'), 'rb').read()
            same = fan.keep_committed('markets_calibration', dict(committed, provenance={'other': 1}), str, root)
            self.assertEqual(open(os.path.join(root, fan.RESULTS, 'markets_calibration.json'), 'rb').read(), before)
            self.assertEqual(same, committed)
            changed = json.loads(json.dumps(committed))
            changed['counts']['live'] += 1
            with self.assertRaises(RuntimeError):
                fan.keep_committed('markets_calibration', changed, str, root)

    def test_the_wording_sentence_is_in_every_fan_markdown_file(self):
        for name in ('results/fan/markets_calibration.md', 'results/fan/ratings_check.md', 'fan/NOTES.md',
                     'fan/FINAL_REPORT.md'):
            self.assertIn(WORDING, ' '.join(read_text(*name.split('/')).split()), name)

    def test_the_reading_in_the_report_and_the_notes_is_the_computed_one(self):
        reading = read_json('results', 'fan', 'ratings.json')['checks']['reading']
        for name in ('results/fan/ratings_check.md', 'fan/NOTES.md'):
            self.assertIn(reading, ' '.join(read_text(*name.split('/')).split()), name)
        self.assertNotIn('underpowered', read_text('results', 'fan', 'ratings_check.md'))
        self.assertNotIn('independent', read_text('results', 'fan', 'ratings_check.md').lower())

    def test_ratings_json_carries_the_labels_on_every_bar(self):
        ratings = fan.load_ratings()
        self.assertEqual(ratings['bar_label'], 'model uncertainty, not measured accuracy')
        for league in ratings['leagues']:
            self.assertEqual(league['defence_bar_note'],
                             "Defence bars do not narrow with more matches. This most likely reflects how the model's "
                             'variance behaves. A simulation reproduced the signs but could not separate this from '
                             'team selection, so treat it as unconfirmed (see ratings_check.md).')
            self.assertNotIn('property of the model', league['defence_bar_note'])
            self.assertTrue(all(t['bar_label'] == ratings['bar_label'] for t in league['teams']))
        self.assertIn(ratings['bar_label'], read_text('results', 'fan', 'ratings_check.md'))
        self.assertIn(fan.DEFENCE_BAR_NOTE, read_text('results', 'fan', 'ratings_check.md'))


class ClaimsTests(unittest.TestCase):
    def test_every_fan_claim_names_a_tracked_source_and_a_script(self):
        claims = [c for c in read_json('results', 'claims.json')['claims'] if c['id'].startswith('fan_')]
        self.assertGreaterEqual(len(claims), 15)
        tracked = set(subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True).stdout.split('\n'))
        for claim in claims:
            self.assertIn(claim['source'], tracked, claim['id'])
            self.assertIn(claim['script'].split()[0], tracked, claim['id'])

    def test_every_number_in_the_fan_deliverables_has_a_claim(self):
        claimed = {str(c['value']) for c in read_json('results', 'claims.json')['claims']}
        names = sorted(f'{folder}/{f}' for folder in ('results/fan', 'fan') for f in os.listdir(path(*folder.split('/')))
                       if f.endswith('.md'))
        self.assertGreaterEqual(len(names), 4)
        for name in names:
            numbers = verify_claims.numbers_in(read_text(*name.split('/')))
            self.assertEqual(sorted(numbers - claimed), [], f'unclaimed numbers in {name}')

    def test_the_claims_figures_are_the_ones_in_the_json_files(self):
        shown = read_json('results', 'fan', 'ratings.json')['checks']['claims_display']
        sim = read_json('results', 'fan', 'ratings_sim.json')['claims_display']
        claims = {c['id']: c['value'] for c in read_json('results', 'claims.json')['claims']}
        self.assertEqual(claims['fan_spearman_defence'], shown['spearman_defence'])
        self.assertEqual(claims['fan_spearman_attack'], shown['spearman_attack'])
        self.assertEqual(claims['fan_n_established'], shown['n_established'])
        self.assertEqual(claims['fan_smallest_significant_rho'], shown['smallest_significant_rho'])
        self.assertEqual(claims['fan_sim_spearman_defence'], sim['spearman_defence'])
        self.assertEqual(claims['fan_sim_seed'], sim['seed'])


class SimulationTests(unittest.TestCase):
    DESIGN = dict(leagues=1, teams=6, seasons=3, relegated=1)

    def model(self):
        model, _ = p2_model.split_params(p2_params())
        return model

    def test_the_simulation_is_deterministic_for_a_pinned_seed(self):
        a = fan.simulate_matches(self.model(), 0.2, seed=fan.SIM_SEED, design=self.DESIGN)
        b = fan.simulate_matches(self.model(), 0.2, seed=fan.SIM_SEED, design=self.DESIGN)
        c = fan.simulate_matches(self.model(), 0.2, seed=fan.SIM_SEED + 1, design=self.DESIGN)
        pd.testing.assert_frame_equal(a, b)
        self.assertFalse(a[['goals_home', 'goals_away']].equals(c[['goals_home', 'goals_away']]))
        self.assertEqual(len(a), 3 * 6 * 5)
        self.assertEqual(fan.SIM_SEED, 20261028)

    def test_the_simulation_runs_through_the_frozen_filter(self):
        frame = fan.simulate_matches(self.model(), 0.2, design=self.DESIGN)
        result = fan.simulation_result(frame, p2_params(), 0.2)
        self.assertGreater(result['n_established'], 0)
        self.assertEqual(result['sd_vs_matches']['defence']['n'], result['n_established'])

    def test_the_committed_simulation_uses_the_pinned_seed_and_design(self):
        sim = read_json('results', 'fan', 'ratings_sim.json')
        self.assertEqual(sim['seed'], fan.SIM_SEED)
        self.assertEqual(sim['design'], fan.SIM_DESIGN)
        self.assertIn('not a football finding', sim['label'])


class OutputTests(unittest.TestCase):
    def test_model_constants_match_the_frozen_candidate(self):
        constants = read_json('results', 'fan', 'model_constants.json')
        frozen = read_json('results', 'p2', 'candidate_p2.json')
        self.assertEqual(constants['home_adv'], frozen['home_adv'])
        self.assertEqual(constants['rho'], frozen['goals_only']['params']['rho'])
        self.assertEqual(constants['params'], frozen['goals_only']['params'])
        self.assertEqual(constants['params_sha256'], frozen['sha256'])
        self.assertEqual(constants['rate_bounds'], list(exp_model.DEFAULT_PARAMS['rate_bounds']))
        self.assertEqual((constants['grid']['market_max_goals'], constants['grid']['model_max_goals']), (30, 10))

    def test_sample_forecasts_reproduce_from_the_rates_and_rho(self):
        samples = read_json('results', 'fan', 'sample_forecasts.json')
        self.assertEqual(len(samples['samples']), fan.SAMPLE_SIZE)
        for sample in samples['samples']:
            again = fan.markets(fan.score_grid(sample['lambda_home'], sample['mu_away'], samples['rho']))
            self.assertEqual(json.loads(json.dumps(again)), sample['markets'])
            self.assertLess(np.abs(np.array([sample['markets'][k] for k in ('home', 'draw', 'away')]) -
                                   np.array(sample['model_1x2_max_goals_10'])).max(), 0.01)


if __name__ == '__main__':
    unittest.main()
