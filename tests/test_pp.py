"""Tests for pp_model and run_pp (pp/PREREGISTRATION_v2.md). The grid checks are synthetic; the real-data checks run
the frozen P2 goals-only filter on the non-TEST rows only (nothing is scored) and are skipped without the local
fixture cache.

Run: python -X utf8 -m pytest -q tests/test_pp.py
"""
import json
import os
import unittest
from unittest import mock

import numpy as np

import exp_model
import p2_model
import pp_model
import run_p2
from data_pipeline import RAW_FIXTURES_PATH
from run_experiments import load_data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RHO = -0.04
BOUNDS = (0.15, 6.0)
STATES = [(np.log(1.4), 0.2, np.log(1.1), 0.18), (np.log(0.9), 0.35, np.log(1.6), 0.31),
          (np.log(2.5), 0.31, np.log(0.6), 0.6), (np.log(0.3), 1.2, np.log(4.0), 0.9)]


def baseline_grid(lambda_home, mu_away, rho):
    """The normalised grid exp_model.dixon_coles_probs builds, captured where it reads the home-win mass."""
    captured, tril = [], np.tril

    def capture(grid, k=0):
        captured.append(np.array(grid, copy=True))
        return tril(grid, k=k)

    with mock.patch.object(exp_model.np, 'tril', side_effect=capture):
        probs = exp_model.dixon_coles_probs(lambda_home, mu_away, rho)
    return captured[0], probs


def explicit_grid(state, rho, bounds, nodes):
    """The node-pair sum written out (one normalised baseline grid per pair), for the separable form to match."""
    x, w = pp_model.nodes_and_weights(nodes)
    total = np.zeros((11, 11))
    for i, lam in enumerate(pp_model.node_rates(state[0], state[1], x, bounds)):
        for j, mu in enumerate(pp_model.node_rates(state[2], state[3], x, bounds)):
            total += w[i] * w[j] * baseline_grid(lam, mu, rho)[0]
    return total


def marginal_moments(grid, axis):
    """(mean, variance) of home goals (axis 1 summed out) or away goals (axis 0 summed out)."""
    pmf = grid.sum(axis=axis)
    goals = np.arange(len(pmf))
    mean = float((goals * pmf).sum())
    return mean, float(((goals - mean) ** 2 * pmf).sum())


class GridTests(unittest.TestCase):
    def test_a_zero_variance_reproduces_the_baseline_grid(self):
        for lam, mu in [(1.45, 1.1), (0.15, 6.0), (2.7, 0.4), (0.9, 0.9), (8.0, 0.05)]:
            for rho in (0.0, RHO):
                clipped = (min(max(lam, BOUNDS[0]), BOUNDS[1]), min(max(mu, BOUNDS[0]), BOUNDS[1]))
                expected, probs = baseline_grid(*clipped, rho)
                for nodes in (9, 301):
                    grid = pp_model.pp_grid(np.log(lam), 0.0, np.log(mu), 0.0, rho, BOUNDS, nodes)
                    self.assertLess(np.abs(grid - expected).max(), 1e-12)
                    self.assertLess(np.abs(np.array(pp_model.outcome_probs(grid)) - probs).max(), 1e-12)

    def test_the_separable_form_equals_the_explicit_node_pair_sum(self):
        for state in STATES:
            for rho in (0.0, RHO, -0.3):
                expected = explicit_grid(state, rho, BOUNDS, 9)
                self.assertLess(np.abs(pp_model.pp_grid(*state, rho, BOUNDS, 9) - expected).max(), 1e-14)

    def test_b_grids_are_non_negative_and_sum_to_one(self):
        for state in STATES:
            for rho in (0.0, RHO, -0.3):
                for nodes in pp_model.LADDER:
                    grid = pp_model.pp_grid(*state, rho, BOUNDS, nodes)
                    self.assertGreaterEqual(grid.min(), 0.0)
                    self.assertLess(abs(grid.sum() - 1.0), 1e-12)
                    self.assertLess(abs(sum(pp_model.outcome_probs(grid)) - 1.0), 1e-12)

    def test_d_mean_goals_exceed_the_plug_in_by_about_exp_half_v(self):
        log_mean_home, v_home, log_mean_away, v_away = np.log(1.4), 0.1, np.log(1.1), 0.08
        mixed = pp_model.pp_grid(log_mean_home, v_home, log_mean_away, v_away, 0.0, None, 21)
        plug_in = pp_model.pp_grid(log_mean_home, 0.0, log_mean_away, 0.0, 0.0, None, 21)
        for axis, v in ((1, v_home), (0, v_away)):
            ratio = marginal_moments(mixed, axis)[0] / marginal_moments(plug_in, axis)[0]
            self.assertGreater(ratio, 1.0)
            self.assertLess(abs(ratio / np.exp(v / 2) - 1.0), 0.01)

    def test_e_goal_variance_is_at_least_the_plug_in_variance(self):
        for log_mean_home, v_home, log_mean_away, v_away in STATES[:3]:
            for nodes in (9, 301):
                mixed = pp_model.pp_grid(log_mean_home, v_home, log_mean_away, v_away, RHO, BOUNDS, nodes)
                plug_in = pp_model.pp_grid(log_mean_home, 0.0, log_mean_away, 0.0, RHO, BOUNDS, nodes)
                for axis in (1, 0):
                    self.assertGreaterEqual(marginal_moments(mixed, axis)[1], marginal_moments(plug_in, axis)[1])

    def test_the_node_rule_picks_the_smallest_qualifying_value(self):
        errors = {9: 3e-5, 21: 2e-5, 41: 9e-6, 81: 1e-6, 161: 1e-7, 301: 0.0}
        self.assertEqual(pp_model.select_nodes(errors), 41)
        self.assertEqual(pp_model.select_nodes({**errors, 41: 1e-5, 81: 2e-5, 161: 1e-4}), 301)


@unittest.skipUnless(os.path.isfile(RAW_FIXTURES_PATH), 'needs the local fixture cache')
class RealDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, 'results', 'p2', 'candidate_p2.json'), encoding='utf-8') as handle:
            frozen = json.load(handle)
        df, _, test_index, _ = load_data()
        cls.work = run_p2.selection_frames(df, test_index)['work']
        cls.params, cls.home_adv = frozen['goals_only']['params'], frozen['home_adv']
        cls.output = pp_model.run_filter(cls.work, cls.params, cls.home_adv, pp_model.LADDER[0])
        cls.model = p2_model.split_params(cls.params)[0]

    def test_the_plug_in_forecast_reproduces_p2_model(self):
        expected = p2_model.run_filter(self.work, self.params, self.home_adv)
        self.assertTrue(self.output.index.equals(expected.index))
        numeric = ['pred_home_win', 'pred_draw', 'pred_away_win', 'lambda_home', 'mu_away', 'shots_weight']
        self.assertLess(np.abs(self.output[numeric].to_numpy() - expected[numeric].to_numpy()).max(), 1e-12)

    def test_c_the_v2_node_rule_runs_and_n_star_meets_the_criterion(self):
        rows = pp_model.selection_rows(self.output)
        self.assertEqual(len(rows), pp_model.SELECTION_ROWS)
        bounds = self.model['rate_bounds'] if self.model['clip_rates'] else None
        errors = pp_model.ladder_errors(rows, self.model['rho'], bounds)
        n_star = pp_model.select_nodes(errors)
        self.assertTrue(n_star == pp_model.REFERENCE_NODES or errors[n_star] < pp_model.NODE_TOLERANCE)
        self.assertTrue(all(errors[n] >= pp_model.NODE_TOLERANCE for n in pp_model.LADDER if n < n_star))
        recorded = os.path.join(ROOT, 'results', 'pp', 'pp_nodes.json')
        if os.path.isfile(recorded):
            with open(recorded, encoding='utf-8') as handle:
                nodes = json.load(handle)
            self.assertEqual(nodes['n_star'], n_star)
            self.assertFalse(nodes['outcomes_used'])
            for n, error in errors.items():
                self.assertAlmostEqual(nodes['max_error'][str(n)], error, delta=1e-15)


if __name__ == '__main__':
    unittest.main()
