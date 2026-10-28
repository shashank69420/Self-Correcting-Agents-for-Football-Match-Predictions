"""Plain-loop recomputation of the final per-team sd values, from the update equations in fan/NOTES.md only.

This does not import fan_features.py. It takes the clipped pre-match rates (lambda, mu) per match from the model's own
output, so it checks the variance bookkeeping and the capture of the final states, not the rates. It is not
independent of the model: the equations in fan/NOTES.md were written by the author of both the code and this test.

Run: python -X utf8 -m pytest -q tests/test_fan_independent.py
"""
import json
import os
import unittest

import live2627
import p2_model
from data_pipeline import RAW_FIXTURES_PATH
from run_experiments import FILTER_COLUMNS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOLERANCE = 1e-9


def read_json(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as handle:
        return json.load(handle)


def final_variances(matches, process_noise, initial_var):
    """NOTES.md steps 1, 4 and 5, plain loops: matches are (home, away, lambda, mu) in processing order."""
    attack, defence = {}, {}
    for home, away, lam, mu in matches:
        for team in (home, away):
            attack.setdefault(team, initial_var)
            defence.setdefault(team, initial_var)
            attack[team] += process_noise  # step 1
            defence[team] += process_noise
        precision_attack_home = 1.0 / attack[home] + lam  # step 4
        precision_defence_away = 1.0 / defence[away] + lam
        precision_attack_away = 1.0 / attack[away] + mu
        precision_defence_home = 1.0 / defence[home] + mu
        attack[home] = 1.0 / precision_attack_home  # step 5
        defence[away] = 1.0 / precision_defence_away
        attack[away] = 1.0 / precision_attack_away
        defence[home] = 1.0 / precision_defence_home
    return attack, defence


class PlainLoopVarianceTests(unittest.TestCase):
    def test_equations_on_two_matches_by_hand(self):
        attack, defence = final_variances([('a', 'b', 1.5, 1.0)], 0.25, 0.75)
        self.assertAlmostEqual(attack['a'], 1.0 / (1.0 / 1.0 + 1.5), places=15)
        self.assertAlmostEqual(defence['b'], 1.0 / (1.0 / 1.0 + 1.5), places=15)
        self.assertAlmostEqual(attack['b'], 1.0 / (1.0 / 1.0 + 1.0), places=15)
        self.assertAlmostEqual(defence['a'], 1.0 / (1.0 / 1.0 + 1.0), places=15)

    @unittest.skipUnless(os.path.isfile(RAW_FIXTURES_PATH), 'needs the local fixture cache')
    def test_final_sd_matches_the_committed_ratings(self):
        params = read_json('results', 'p2', 'candidate_p2.json')['goals_only']['params']
        history = live2627.load_history()
        live = live2627.live_frame(live2627.read_json(live2627.snapshot_name('20261026'))['rows'])
        both, _ = live2627.concatenate(history, live)
        output = p2_model.run_filter(both[FILTER_COLUMNS + list(p2_model.SOT_COLUMNS)], params, live2627.HOME_ADV)
        attack, defence = final_variances(
            zip(output['team_home'], output['team_away'], output['lambda_home'], output['mu_away']),
            params['process_noise'], params['initial_var'])
        checked, worst = 0, 0.0
        for league in read_json('results', 'fan', 'ratings.json')['leagues']:
            for team in league['teams']:
                worst = max(worst, abs(attack[team['team']] ** 0.5 - team['attack_sd']),
                            abs(defence[team['team']] ** 0.5 - team['defence_sd']))
                checked += 1
        self.assertGreater(checked, 140)
        self.assertLess(worst, TOLERANCE)


if __name__ == '__main__':
    unittest.main()
