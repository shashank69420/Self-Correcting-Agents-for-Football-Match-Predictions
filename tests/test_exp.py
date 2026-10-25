"""Synthetic, network-free tests for exp_model.py and exp_harness.py.

Run: python -X utf8 -m unittest tests.test_exp -v
"""
import unittest

import numpy as np
import pandas as pd

import exp_harness as harness
from exp_model import (DEFAULT_PARAMS, LeagueEffects, apply_calibration, dixon_coles_probs,
                       fit_calibration, make_params, run_filter)
from metrics import paired_week_block_ci
from stage2_dynamic import TeamState, match_prediction_probs, run_sequential_filter
from stage3_detector import run_change_filter

HOME_ADV = 0.2
PROBS = ['pred_home_win', 'pred_draw', 'pred_away_win']


def round_robin(teams):
    teams = list(teams)
    rounds = []
    for _ in range(len(teams) - 1):
        rounds.append([(teams[i], teams[-1 - i]) for i in range(len(teams) // 2)])
        teams = [teams[0], teams[-1]] + teams[1:-1]
    return rounds + [[(away, home) for home, away in matches] for matches in rounds]


def synthetic_fixtures(seed=0, n_seasons=3):
    """Two leagues, six teams each; two promoted teams per league per later season.
    Every round of both leagues shares one kickoff, so timestamps tie within and across leagues."""
    rng = np.random.default_rng(seed)
    leagues = {'L1': [f'A{i}' for i in range(6)], 'L2': [f'B{i}' for i in range(6)]}
    rows, new_team = [], 0
    for season_number in range(n_seasons):
        season = f'{2019 + season_number}-{2020 + season_number}'
        start = pd.Timestamp(f'{2019 + season_number}-08-03 15:00')
        for league, teams in leagues.items():
            if season_number > 0:
                teams[-2:] = [f'{league}_new{new_team}', f'{league}_new{new_team + 1}']
                new_team += 2
                rng.shuffle(teams)
            for number, matches in enumerate(round_robin(teams)):
                for home, away in matches:
                    rows.append(dict(date=start + pd.Timedelta(days=7 * number), team_home=home,
                                     team_away=away, goals_home=int(rng.poisson(1.5)),
                                     goals_away=int(rng.poisson(1.1)), season=season, competition=league))
    return pd.DataFrame(rows).sort_values('date', kind='stable').reset_index(drop=True)


class DefaultParamsTest(unittest.TestCase):
    def test_defaults_reproduce_stage2(self):
        df = synthetic_fixtures()
        exp = run_filter(df, DEFAULT_PARAMS, HOME_ADV)
        stage2, _ = run_sequential_filter(df, HOME_ADV)
        export, _ = run_change_filter(df, 0.0, home_adv=HOME_ADV)
        self.assertTrue(exp.index.equals(stage2.index))
        self.assertEqual(list(exp.columns), list(export.columns))
        self.assertLessEqual(np.abs(exp[PROBS].to_numpy() - stage2[PROBS].to_numpy()).max(), 1e-12)
        self.assertLessEqual(np.abs(exp[PROBS].to_numpy() - export[PROBS].to_numpy()).max(), 1e-12)
        np.testing.assert_array_equal(exp[['lambda_home', 'mu_away']].to_numpy(),
                                      export[['lambda_home', 'mu_away']].to_numpy())

    def test_zero_drift_extras_equal_baseline(self):
        df = synthetic_fixtures()
        base = run_filter(df, DEFAULT_PARAMS, HOME_ADV)
        zero = run_filter(df, make_params(drift_per_day=0.0, season_var=0.0, drift_cap_days=10.0), HOME_ADV)
        pd.testing.assert_frame_equal(base, zero)
        drift = run_filter(df, make_params(drift_per_day=0.0005, season_var=0.05), HOME_ADV)
        self.assertGreater(np.abs(drift[PROBS].to_numpy() - base[PROBS].to_numpy()).max(), 0)
        self.assertTrue((drift.extra_process_variance >= 0).all())

    def test_unknown_parameter_is_rejected(self):
        with self.assertRaises(KeyError):
            make_params(process_nosie=0.02)


class TestRowsTest(unittest.TestCase):
    def frame(self):
        dates = pd.to_datetime(['2020-01-05 15:00', '2020-08-01 15:00', '2022-03-01 15:00', '2023-08-01 15:00',
                                '2024-01-01 13:00', '2024-01-01 13:00', '2024-02-01 15:00'])
        return pd.DataFrame(dict(date=dates, goals_home=[1, 0, 2, 1, 1, 0, 3], goals_away=[0, 0, 1, 2, 1, 1, 0],
                                 pred_home_win=0.45, pred_draw=0.27, pred_away_win=0.28))

    def test_split_excludes_test_rows_sharing_a_kickoff(self):
        df = self.frame()
        test_index = df.index[5:]  # row 4 is training and shares row 5's kickoff
        splits = harness.split_index(df, test_index)
        self.assertEqual(list(splits['burn_in']), [0])
        self.assertEqual(list(splits['dev']), [1, 2])
        self.assertEqual(list(splits['val']), [3, 4])

    def test_test_row_cannot_be_scored(self):
        df = self.frame()
        test_index = df.index[5:]
        harness.summary(df.loc[[3, 4]], test_index)
        for call in (lambda: harness.summary(df.loc[[4, 5]], test_index),
                     lambda: harness.scored(df.loc[[6]], test_index),
                     lambda: harness.climatology(df, test_index)):
            with self.assertRaises(AssertionError):
                call()


class DrawCorrectionTest(unittest.TestCase):
    def test_rho_zero_equals_stage2_grid(self):
        for attack, defence in [(0.0, 0.0), (0.4, -0.3), (-1.2, 0.9)]:
            home, away = TeamState(), TeamState()
            home.attack_mean, away.defence_mean = attack, defence
            away.attack_mean, home.defence_mean = defence / 2, attack / 3
            lam = np.exp(home.attack_mean + away.defence_mean + HOME_ADV)
            mu = np.exp(away.attack_mean + home.defence_mean)
            self.assertEqual(dixon_coles_probs(lam, mu, 0.0), match_prediction_probs(home, away, HOME_ADV))

    def test_any_rho_renormalises_and_negative_rho_adds_draws(self):
        for lam, mu in [(1.4, 1.1), (0.3, 0.2), (7.0, 0.5)]:
            draw_zero = dixon_coles_probs(lam, mu, 0.0)[1]
            for rho in (-0.04, -0.08, -0.12, -0.16, 0.1):
                probs = dixon_coles_probs(lam, mu, rho)
                self.assertAlmostEqual(sum(probs), 1.0, places=12)
                self.assertTrue(min(probs) >= 0)
                if rho < 0:
                    self.assertGreater(probs[1], draw_zero)


class CalibrationTest(unittest.TestCase):
    def test_calibrated_probabilities_sum_to_one(self):
        rng = np.random.default_rng(1)
        probs = rng.dirichlet([4, 2.5, 3], size=500)
        np.testing.assert_allclose(apply_calibration(probs, 1.0, [0, 0, 0]), probs, atol=1e-12)
        for temperature, bias in [(0.7, [0.1, 0.05, -0.15]), (1.6, [-0.3, 0.2, 0.1])]:
            calibrated = apply_calibration(probs, temperature, bias)
            np.testing.assert_allclose(calibrated.sum(axis=1), 1.0, atol=1e-12)
        actual = np.array([rng.choice(3, p=p) for p in apply_calibration(probs, 0.8, [0.1, 0.1, -0.2])])
        temperature, bias = fit_calibration(probs, actual)
        self.assertAlmostEqual(sum(bias), 0.0, places=12)
        self.assertGreater(temperature, 0)
        with self.assertRaises(ValueError):
            apply_calibration(probs, 1.0, [0.1, 0.0, 0.0])


class AcceptanceTest(unittest.TestCase):
    def test_rule(self):
        self.assertTrue(harness.accept(1.00, 0.99, 1.00, 0.99, -0.001)[0])
        self.assertFalse(harness.accept(1.00, 0.99, 1.00, 1.01, -0.001)[0])  # VAL worsens
        self.assertFalse(harness.accept(1.00, 0.99, 1.00, 1.00, -0.001)[0])  # VAL ties
        self.assertFalse(harness.accept(1.00, 1.01, 1.00, 0.99, -0.001)[0])  # DEV worsens
        self.assertFalse(harness.accept(1.00, 0.99, 1.00, 0.99, 0.0)[0])     # CI touches 0

    def test_week_block_ci_matches_metrics_helper(self):
        rng = np.random.default_rng(2)
        dates = pd.Series(pd.date_range('2021-01-01', periods=600, freq='13h'))
        delta = rng.normal(-0.001, 0.05, size=600)
        low, high, _ = harness.week_block_ci(delta, dates, level=0.95, seed=20260922)
        np.testing.assert_allclose([low, high], paired_week_block_ci(delta, dates), rtol=0, atol=1e-15)
        wide_low, wide_high, p_value = harness.week_block_ci(delta, dates)
        self.assertLessEqual(wide_low, low)
        self.assertGreaterEqual(wide_high, high)
        self.assertTrue(0 < p_value <= 1)

    def test_holm(self):
        np.testing.assert_allclose(harness.holm([0.01, 0.04, 0.03, 0.5]), [0.04, 0.09, 0.09, 0.5])


class LeagueEffectsTest(unittest.TestCase):
    def test_offsets_ignore_pending_matches(self):
        effects = LeagueEffects(100)
        self.assertEqual(effects.offsets('L1'), (0.0, 0.0))
        effects.observe('L1', 3, 0)
        self.assertEqual(effects.offsets('L1'), (0.0, 0.0))
        effects.commit()
        effects.observe('L2', 0, 2)
        effects.commit()
        self.assertGreater(effects.offsets('L1')[0], 0)
        self.assertEqual(effects.offsets('L3'), (0.0, 0.0))

    def test_league_effects_use_only_strictly_earlier_matches(self):
        df = synthetic_fixtures()
        params = make_params(league_k=100)
        base = run_filter(df, params, HOME_ADV)
        cut = df.date.drop_duplicates().iloc[12]
        changed = df.copy()
        later = changed.date >= cut
        changed.loc[later, 'goals_home'] = 7
        changed.loc[later, 'goals_away'] = 0
        perturbed = run_filter(changed, params, HOME_ADV)
        upto = df.index[df.date <= cut]  # includes every match at the perturbed kickoff
        pd.testing.assert_frame_equal(base.loc[upto, ['lambda_home', 'mu_away'] + PROBS],
                                      perturbed.loc[upto, ['lambda_home', 'mu_away'] + PROBS])
        after = df.index[df.date > cut]
        self.assertGreater(np.abs(base.loc[after, 'lambda_home'] - perturbed.loc[after, 'lambda_home']).max(), 0)


class ColdStartAndClipTest(unittest.TestCase):
    def test_rate_clip_respects_bounds(self):
        rows = [dict(date=pd.Timestamp('2020-01-01') + pd.Timedelta(days=7 * i), team_home='Big',
                     team_away=f'Small{i}', goals_home=9, goals_away=0, season='2019-2020', competition='L1')
                for i in range(6)]
        rows += [dict(date=pd.Timestamp('2020-03-01'), team_home='Small0', team_away='Big',
                      goals_home=0, goals_away=9, season='2019-2020', competition='L1')]
        df = pd.DataFrame(rows)
        unclipped = run_filter(df, DEFAULT_PARAMS, HOME_ADV)
        self.assertGreater(max(unclipped.lambda_home.max(), unclipped.mu_away.max()), 6.0)
        clipped = run_filter(df, make_params(clip_rates=True), HOME_ADV)
        for column in ('lambda_home', 'mu_away'):
            self.assertTrue(clipped[column].between(0.15, 6.0).all())

    def test_cold_start_only_for_late_teams(self):
        df = synthetic_fixtures()
        a, d = 0.3, 0.15
        base = run_filter(df, DEFAULT_PARAMS, HOME_ADV)
        cold = run_filter(df, make_params(cold_attack=a, cold_defence=d), HOME_ADV)
        late = df.team_home.str.contains('new') | df.team_away.str.contains('new')
        first_late = df.index[late][0]
        before = df.index[:first_late]
        pd.testing.assert_frame_equal(base.loc[before], cold.loc[before])
        row = df.loc[first_late]
        home_new, away_new = 'new' in row.team_home, 'new' in row.team_away
        # lambda = exp(home attack + away defence + adv); mu = exp(away attack + home defence).
        self.assertAlmostEqual(cold.lambda_home[first_late],
                               base.lambda_home[first_late] * np.exp(-a * home_new + d * away_new), places=12)
        self.assertAlmostEqual(cold.mu_away[first_late],
                               base.mu_away[first_late] * np.exp(-a * away_new + d * home_new), places=12)
        # Every row of the first season involves only original teams and is unchanged.
        first_season = df.index[df.season == '2019-2020']
        pd.testing.assert_frame_equal(base.loc[first_season], cold.loc[first_season])


if __name__ == '__main__':
    unittest.main()
