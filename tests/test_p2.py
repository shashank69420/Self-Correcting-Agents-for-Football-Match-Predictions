"""Synthetic, network-free tests for the P2 modules (p2_data, p2_model, p2_stack, run_p2).

Run: python -X utf8 -m pytest -q tests/test_p2.py
"""
import os
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd

import exp_harness as harness
import p2_data
import p2_model
import p2_stack
import run_p2
from exp_model import make_params, run_filter as exp_run_filter

HOME_ADV = 0.2
PROBS = ['pred_home_win', 'pred_draw', 'pred_away_win']
P1 = dict(process_noise=0.005, initial_var=0.3, cold_defence=0.3, clip_rates=True, rho=-0.04)


def round_robin(teams):
    teams = list(teams)
    rounds = []
    for _ in range(len(teams) - 1):
        rounds.append([(teams[i], teams[-1 - i]) for i in range(len(teams) // 2)])
        teams = [teams[0], teams[-1]] + teams[1:-1]
    return rounds + [[(away, home) for home, away in matches] for matches in rounds]


def fixtures(seed=0, n_seasons=3, first_year=2019, step_days=7):
    """Two leagues of six teams with shots on target; two promoted teams per league per later season."""
    rng = np.random.default_rng(seed)
    leagues = {'L1': [f'A{i}' for i in range(6)], 'L2': [f'B{i}' for i in range(6)]}
    rows, new_team = [], 0
    for number_season in range(n_seasons):
        season = f'{first_year + number_season}-{first_year + number_season + 1}'
        start = pd.Timestamp(f'{first_year + number_season}-08-03 15:00')
        for league, teams in leagues.items():
            if number_season > 0:
                teams[-2:] = [f'{league}_new{new_team}', f'{league}_new{new_team + 1}']
                new_team += 2
            for number, matches in enumerate(round_robin(teams)):
                for home, away in matches:
                    goals_home, goals_away = int(rng.poisson(1.5)), int(rng.poisson(1.1))
                    rows.append(dict(date=start + pd.Timedelta(days=step_days * number), team_home=home,
                                     team_away=away, goals_home=goals_home, goals_away=goals_away,
                                     hst=float(goals_home + rng.poisson(3)), ast=float(goals_away + rng.poisson(2)),
                                     season=season, competition=league))
    return pd.DataFrame(rows).sort_values('date', kind='stable').reset_index(drop=True)


class ShotsWeightZeroTest(unittest.TestCase):
    def test_w0_reproduces_p1(self):
        df = fixtures()
        reference = exp_run_filter(df, make_params(**P1), HOME_ADV)
        ours = p2_model.run_filter(df, dict(P1, shots_w=0.0), HOME_ADV)
        self.assertTrue(ours.index.equals(reference.index))
        columns = PROBS + ['lambda_home', 'mu_away']
        self.assertLessEqual(np.abs(ours[columns].to_numpy() - reference[columns].to_numpy()).max(), 1e-12)
        self.assertTrue((ours.shots_weight == 0).all())

    def test_unsupported_params_raise(self):
        with self.assertRaises(ValueError):
            p2_model.run_filter(fixtures(n_seasons=1), dict(P1, drift_per_day=0.001), HOME_ADV)


class ShotsScaleTest(unittest.TestCase):
    def test_scale_uses_strictly_earlier_rows_only(self):
        df = fixtures()
        with mock.patch.object(p2_model, 'SHOTS_MIN_MATCHES', 5):
            scale = p2_model.shots_scale(df)
            cutoff = df.date.unique()[8]
            changed = df.copy()
            later = changed.date >= cutoff
            changed.loc[later, ['goals_home', 'hst']] = changed.loc[later, ['goals_home', 'hst']] * 3 + 1
            changed_scale = p2_model.shots_scale(changed)
        upto = (df.date <= cutoff).to_numpy()
        np.testing.assert_array_equal(scale[upto], changed_scale[upto])
        # One row checked by hand: its league, dated strictly before it.
        row = df.index[(df.date == cutoff) & (df.competition == 'L1')][0]
        earlier = df.loc[(df.date < cutoff) & (df.competition == 'L1')]
        expected = (earlier.goals_home + earlier.goals_away).sum() / (earlier.hst + earlier.ast).sum()
        self.assertAlmostEqual(scale[row], expected, places=12)

    def test_minimum_and_pooled_fallback(self):
        df = fixtures(n_seasons=1)
        first_day = df.date == df.date.min()
        self.assertTrue(np.isnan(p2_model.shots_scale(df)[first_day.to_numpy()]).all())
        # League L2 without shots: its rows fall back to the pooled scale from L1.
        df.loc[df.competition == 'L2', ['hst', 'ast']] = np.nan
        with mock.patch.object(p2_model, 'SHOTS_MIN_MATCHES', 5):
            scale = p2_model.shots_scale(df)
        row = df.index[(df.competition == 'L2') & (df.date == df.date.unique()[6])][0]
        earlier = df.loc[(df.date < df.date[row]) & (df.competition == 'L1')]
        expected = (earlier.goals_home + earlier.goals_away).sum() / (earlier.hst + earlier.ast).sum()
        self.assertAlmostEqual(scale[row], expected, places=12)

    def test_shots_never_enter_the_same_match_forecast(self):
        df = fixtures()
        params = dict(P1, shots_w=0.5)
        with mock.patch.object(p2_model, 'SHOTS_MIN_MATCHES', 5):
            base = p2_model.run_filter(df, params, HOME_ADV)
            changed = df.copy()
            row = df.index[len(df) // 2]
            changed.loc[row, 'hst'] += 7
            other = p2_model.run_filter(changed, params, HOME_ADV)
        self.assertGreater(base.shots_weight[row], 0)
        upto = df.date <= df.date[row]
        np.testing.assert_array_equal(base.loc[upto, PROBS].to_numpy(), other.loc[upto, PROBS].to_numpy())
        later = df.date > df.date[row]
        self.assertGreater(np.abs(base.loc[later, PROBS].to_numpy() - other.loc[later, PROBS].to_numpy()).max(), 0)


class MissingShotsTest(unittest.TestCase):
    def test_missing_sot_gives_weight_zero(self):
        df = fixtures()
        rows = df.index[[100, 101, 102]]
        df.loc[rows[0], 'hst'] = np.nan
        df.loc[rows[1], 'ast'] = np.nan
        with mock.patch.object(p2_model, 'SHOTS_MIN_MATCHES', 5):
            y_home, y_away, weight = p2_model.effective_goals(df, 0.5)
        self.assertEqual(weight[100], 0.0)
        self.assertEqual(weight[101], 0.0)
        self.assertEqual(weight[102], 0.5)
        for position in (100, 101):
            self.assertEqual(y_home[position], df.goals_home.iloc[position])
            self.assertEqual(y_away[position], df.goals_away.iloc[position])
        self.assertTrue(np.isfinite(y_home).all() and np.isfinite(y_away).all())

    def test_no_shot_columns_gives_weight_zero(self):
        df = fixtures(n_seasons=1).drop(columns=['hst', 'ast'])
        _, _, weight = p2_model.effective_goals(df, 0.75)
        self.assertTrue((weight == 0).all())


class StackTest(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(3)
        self.n = 900
        self.model = rng.dirichlet([4, 3, 3], size=self.n)
        self.market = rng.dirichlet([5, 3, 3], size=self.n)
        self.actual = np.array([rng.choice(3, p=p) for p in 0.5 * self.model + 0.5 * self.market])
        self.dates = pd.Series(pd.date_range('2019-08-01', periods=self.n, freq='2D'))

    def test_a_zero_equals_market_only(self):
        coef = dict(a=0.0, b=1.3, c=[0.1, -0.04, -0.06])
        stacked = p2_stack.apply(coef, self.model, self.market)
        logits = 1.3 * np.log(self.market) + np.array(coef['c'])
        expected = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)
        np.testing.assert_allclose(stacked, expected, atol=1e-14)
        np.testing.assert_allclose(stacked, p2_stack.apply(coef, np.full_like(self.model, 1 / 3), self.market),
                                   atol=1e-14)
        market_only = p2_stack.fit(self.model, self.market, self.actual, with_model=False)
        self.assertEqual(market_only['a'], 0.0)
        np.testing.assert_allclose(p2_stack.apply(market_only, self.model, self.market),
                                   p2_stack.apply(dict(market_only, a=0.0), self.market, self.market), atol=1e-14)

    def test_fit_uses_dev_rows_only(self):
        has = np.ones(self.n, bool)
        mask = p2_stack.dev_mask(self.dates, has)
        self.assertTrue(mask.any() and (~mask).any())
        dev_dates = self.dates[mask]
        self.assertTrue((dev_dates >= harness.DEV_START).all() and (dev_dates < harness.VAL_START).all())
        base = p2_stack.fit_dev(self.dates, self.model, self.market, self.actual, has)
        changed = self.actual.copy()
        changed[~mask] = (changed[~mask] + 1) % 3
        market = self.market.copy()
        market[~mask] = np.nan  # rows outside DEV may even be unusable
        self.assertEqual(base, p2_stack.fit_dev(self.dates, self.model, market, changed, has))
        changed_dev = self.actual.copy()
        changed_dev[mask] = (changed_dev[mask] + 1) % 3
        self.assertNotEqual(base['a'], p2_stack.fit_dev(self.dates, self.model, self.market, changed_dev, has)['a'])
        self.assertEqual(base['n'], int(mask.sum()))


class FreshGuardTest(unittest.TestCase):
    def test_guard_raises_without_frozen_file(self):
        fresh = pd.DataFrame(dict(season=['2015-2016'], date=[pd.Timestamp('2015-09-01')]))
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(RuntimeError):
                p2_data.require_frozen(root)
            with self.assertRaises(RuntimeError):
                p2_data.fresh_scoring_rows(fresh, root)
            # Present but not committed (no repository) still refuses.
            os.makedirs(os.path.join(root, 'results', 'p2'))
            with open(os.path.join(root, p2_data.FROZEN), 'w', encoding='utf-8') as handle:
                handle.write('{}')
            with self.assertRaises(RuntimeError):
                p2_data.fresh_scoring_rows(fresh, root)


class SelectionFramesTest(unittest.TestCase):
    def test_no_test_index_row_reaches_selection(self):
        df = fixtures(n_seasons=7, step_days=3)
        for column in p2_data.SNAPSHOT_TRIPLE:
            df[column] = 2.5
        test_index = df.index[int(len(df) * 0.8):]
        frames = run_p2.selection_frames(df, test_index)
        for name, frame in frames.items():
            self.assertFalse(frame.index.isin(test_index).any(), name)
        self.assertGreater(len(frames['dev']), 0)
        self.assertGreater(len(frames['val']), 0)
        self.assertEqual(len(frames['work']), len(df) - len(test_index))
        with self.assertRaises(AssertionError):
            harness.assert_no_test(df.loc[frames['work'].index.union(test_index[:1])], test_index)


class AcceptanceRuleTest(unittest.TestCase):
    def test_rejects_when_val_worsens(self):
        accepted, checks = run_p2.decide(1.00, 0.99, 1.00, 1.001, -0.002)
        self.assertFalse(accepted)
        self.assertFalse(checks['(ii) VAL log-loss improves'])
        self.assertTrue(run_p2.decide(1.00, 0.99, 1.00, 0.999, -0.002)[0])
        self.assertFalse(run_p2.decide(1.00, 0.99, 1.00, 0.999, 0.0)[0])
        self.assertFalse(run_p2.decide(1.00, 1.00, 1.00, 0.999, -0.002)[0])


class FreshSetTest(unittest.TestCase):
    def raw(self, season):
        return pd.DataFrame(dict(competition='L1', season=season, date=pd.to_datetime(['2016-01-02', '2016-01-03']),
                                 team_home=['A', 'B'], team_away=['B', 'A'], goals_home=[1, 0], goals_away=[0, 2]))

    def test_no_season_after_2018_2019(self):
        self.assertEqual(max(p2_data.FRESH_SEASONS), '2018-2019')
        self.assertEqual(p2_data.SCORED_SEASONS, ['2015-2016', '2016-2017', '2017-2018', '2018-2019'])
        self.assertNotIn(p2_data.BURN_IN_SEASON, p2_data.SCORED_SEASONS)
        with self.assertRaises(ValueError):
            p2_data.clean_fresh(self.raw('2019-2020'))
        late = self.raw('2018-2019').assign(date=pd.to_datetime(['2019-08-10', '2019-08-11']))
        with self.assertRaises(AssertionError):
            p2_data.clean_fresh(late)

    def test_datetime_fallback_without_time_column(self):
        fresh = p2_data.clean_fresh(self.raw('2015-2016'))
        self.assertEqual(len(fresh), 2)
        self.assertTrue((fresh.date == pd.to_datetime(['2016-01-02', '2016-01-03'])).all())


if __name__ == '__main__':
    unittest.main()
