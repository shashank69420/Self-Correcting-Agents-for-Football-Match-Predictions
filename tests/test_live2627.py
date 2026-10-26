"""Network-free tests for live2627.py (synthetic data, plus the local fixture cache where noted).

Run: python -X utf8 -m pytest -q tests/test_live2627.py
"""
import os
import shutil
import subprocess
import tempfile
import unittest

import numpy as np
import pandas as pd

import live2627 as live
from data_pipeline import RAW_FIXTURES_PATH
from exp_model import DEFAULT_PARAMS, make_params
from exp_model import run_filter as exp_run_filter
from stage2_dynamic import run_sequential_filter

HOME_ADV = 0.2
P1 = dict(process_noise=0.005, initial_var=0.3, cold_defence=0.3, clip_rates=True, rho=-0.04)
LEAGUES = ('ENG Premier League', 'ESP La Liga')
PROBS = ['pred_home_win', 'pred_draw', 'pred_away_win']


def round_robin(teams):
    teams = list(teams)
    rounds = []
    for _ in range(len(teams) - 1):
        rounds.append([(teams[i], teams[-1 - i]) for i in range(len(teams) // 2)])
        teams = [teams[0], teams[-1]] + teams[1:-1]
    return rounds + [[(away, home) for home, away in matches] for matches in rounds]


def match(rng, league, season, date, home, away):
    goals_home, goals_away = int(rng.poisson(1.5)), int(rng.poisson(1.1))
    return dict(competition=league, season=season, date=date, team_home=home, team_away=away, goals_home=goals_home,
                goals_away=goals_away, hst=float(goals_home + rng.poisson(3)), ast=float(goals_away + rng.poisson(2)),
                avg_ch=2.2, avg_cd=3.3, avg_ca=3.4)


def history(seed=0, n_seasons=3, n_test=120):
    """Synthetic H: two leagues of ten teams, double round robin per season; the last n_test rows flagged TEST."""
    rng = np.random.default_rng(seed)
    rows = []
    for number in range(n_seasons):
        season = f'{2019 + number}-{2020 + number}'
        start = pd.Timestamp(f'{2019 + number}-08-03 15:00')
        for offset, league in enumerate(LEAGUES):
            teams = [f'{league[:3]} {i}' for i in range(10)]
            for week, matches in enumerate(round_robin(teams)):
                for slot, (home, away) in enumerate(matches):
                    rows.append(match(rng, league, season, start + pd.Timedelta(days=7 * week, hours=slot + offset),
                                      home, away))
    frame = pd.DataFrame(rows).sort_values('date', kind='stable').reset_index(drop=True)
    return frame.assign(frame='H', is_test=frame.index >= len(frame) - n_test)


def live_rows(h, seed=1, rounds=6, renamed=None, newcomer='Brand New FC'):
    """Snapshot-style 2026-2027 rows: the H teams of each league, one replaced by a newcomer in the first league and,
    optionally, one renamed (renamed = (old, new)) in the second."""
    rng = np.random.default_rng(seed)
    rows = []
    for offset, league in enumerate(LEAGUES):
        teams = sorted(set(h.loc[h['competition'] == league, 'team_home']))
        if offset == 0 and newcomer:
            teams[-1] = newcomer
        if offset == 1 and renamed:
            teams[teams.index(renamed[0])] = renamed[1]
        for week, matches in enumerate(round_robin(teams)[:rounds]):
            for slot, (home, away) in enumerate(matches):
                row = match(rng, league, live.SEASON, pd.Timestamp('2026-08-15 15:00')
                            + pd.Timedelta(days=7 * week, hours=slot + offset), home, away)
                rows.append(dict(league=league, season=live.SEASON, datetime=row['date'].strftime('%Y-%m-%dT%H:%M:%S'),
                                 home=home, away=away, **{k: row[k] for k in live.SNAPSHOT_FIELDS[5:]}))
    return rows


def concatenated(seed=0):
    h = history(seed)
    both, _ = live.concatenate(h, live.live_frame(live_rows(h)))
    return h, both


class ForecastTest(unittest.TestCase):
    def test_w0_equals_p1_on_concatenated_frame(self):
        _, both = concatenated()
        reference = exp_run_filter(both[live.FILTER_COLUMNS], make_params(**P1), HOME_ADV)
        ours = live.p2_model.run_filter(both[live.FILTER_COLUMNS + live.SOT], dict(P1, shots_w=0.0), HOME_ADV)
        columns = PROBS + ['lambda_home', 'mu_away']
        self.assertTrue(ours.index.equals(reference.index))
        self.assertLessEqual(np.abs(ours[columns].to_numpy() - reference[columns].to_numpy()).max(), 1e-12)
        _, checks = live.forecasts(both, P1, live.P2_PARAMS, HOME_ADV)
        self.assertTrue(all(value <= 1e-12 for value in checks.values()))

    @unittest.skipUnless(os.path.exists(RAW_FIXTURES_PATH), 'needs the local fixture cache')
    def test_w0_equals_p1_on_cached_history(self):
        h = live.load_history()
        last = h.loc[h['season'] == '2025-2026']
        rng, rows = np.random.default_rng(2), []
        for offset, league in enumerate(LEAGUES):
            teams = sorted(set(last.loc[last['competition'] == league, 'team_home']))[:10]
            for week, matches in enumerate(round_robin(teams)[:3]):
                for slot, (home, away) in enumerate(matches):
                    row = match(rng, league, live.SEASON, pd.Timestamp('2026-08-15 15:00')
                                + pd.Timedelta(days=7 * week, hours=slot + offset), home, away)
                    rows.append(dict(league=league, season=live.SEASON, home=home, away=away,
                                     datetime=row['date'].strftime('%Y-%m-%dT%H:%M:%S'),
                                     **{k: row[k] for k in live.SNAPSHOT_FIELDS[5:]}))
        both, _ = live.concatenate(h, live.live_frame(rows))
        _, checks = live.forecasts(both, P1, live.P2_PARAMS)
        self.assertEqual(len(checks), 2)
        self.assertTrue(all(value <= 1e-12 for value in checks.values()), checks)

    def test_m0_is_exp_model_default_and_stage2(self):
        _, both = concatenated()
        result, _ = live.forecasts(both, P1, live.P2_PARAMS, HOME_ADV)
        default = exp_run_filter(both[live.FILTER_COLUMNS], DEFAULT_PARAMS, HOME_ADV)
        stage2, _ = run_sequential_filter(both[live.FILTER_COLUMNS], HOME_ADV)
        for reference in (default, stage2):
            self.assertTrue(result['M0'].index.equals(reference.index))
            self.assertLessEqual(np.abs(result['M0'][PROBS].to_numpy() - reference[PROBS].to_numpy()).max(), 1e-12)

    def test_forecast_unchanged_when_later_rows_removed(self):
        _, both = concatenated()
        full, _ = live.forecasts(both, P1, live.P2_PARAMS, HOME_ADV)
        live_dates = both.loc[both['frame'] == 'L', 'date']
        cutoff = live_dates.sort_values().iloc[len(live_dates) // 2]
        early = both.loc[both['date'] < cutoff]
        truncated, _ = live.forecasts(early, P1, live.P2_PARAMS, HOME_ADV)
        self.assertGreater((full['M2'].loc[both['frame'] == 'L', 'shots_weight'] > 0).sum(), 0)
        for name in ('M0', 'M1', 'M2'):
            columns = PROBS + ['lambda_home', 'mu_away']
            difference = np.abs(full[name].loc[early.index, columns].to_numpy()
                                - truncated[name].loc[early.index, columns].to_numpy()).max()
            self.assertEqual(difference, 0.0, name)


class ScoredFrameTest(unittest.TestCase):
    def test_scored_frame_contains_no_h_or_test_row(self):
        h, both = concatenated()
        scored, logged, named = live.select_scored(both, h, set(), [])
        self.assertTrue((scored['frame'] == 'L').all())
        self.assertFalse(scored['is_test'].any())
        self.assertEqual(set(scored['season']), {live.SEASON})
        self.assertEqual(len(scored), int((both['frame'] == 'L').sum()))
        self.assertEqual((len(logged), len(named)), (0, 0))
        test_row = both.loc[both['is_test']].iloc[[0]]
        with self.assertRaises(AssertionError):
            live.assert_live_only(pd.concat([scored, test_row]), h)
        relabelled = both.loc[~both['is_test'] & (both['frame'] == 'H')].iloc[[0]].assign(frame='L',
                                                                                           season=live.SEASON)
        with self.assertRaises(AssertionError):  # an H key, even relabelled, never enters
            live.assert_live_only(pd.concat([scored, relabelled]), h)

    def test_forward_logged_fixtures_are_excluded(self):
        h, both = concatenated()
        first = both.loc[both['frame'] == 'L'].iloc[0]
        key = (first['competition'], first['season'], first['team_home'], first['team_away'])
        scored, logged, _ = live.select_scored(both, h, {key, ('ESP La Liga', live.SEASON, 'x', 'y')}, [])
        self.assertEqual(len(logged), 1)
        self.assertNotIn(key, set(zip(scored['competition'], scored['season'], scored['team_home'],
                                      scored['team_away'])))
        self.assertEqual(len(scored), int((both['frame'] == 'L').sum()) - 1)

    def test_similar_newcomer_name_is_flagged_and_excluded(self):
        h = history()
        h = h.replace({'team_home': {'ESP 3': "Nott'm Forest"}, 'team_away': {'ESP 3': "Nott'm Forest"}})
        rows = live_rows(h, renamed=("Nott'm Forest", 'Nottm Forest'))
        names, _, _ = live.data_checks(h, live.live_frame(rows))
        flags = dict(zip(names['team'], names['flagged']))
        self.assertEqual(flags, {'Brand New FC': False, 'Nottm Forest': True})
        both, _ = live.concatenate(h, live.live_frame(rows))
        scored, _, named = live.select_scored(both, h, set(), ['Nottm Forest'])
        self.assertGreater(len(named), 0)
        self.assertFalse((scored['team_home'] == 'Nottm Forest').any() or (scored['team_away'] == 'Nottm Forest').any())
        self.assertTrue((scored['team_home'] == 'Brand New FC').any() or (scored['team_away'] == 'Brand New FC').any())

    def test_more_than_four_newcomers_in_a_league_stops(self):
        h = history()
        rows = live_rows(h)
        renames = {f'ENG {i}': f'Unseen {i}' for i in range(4)}
        for row in rows:
            row['home'], row['away'] = renames.get(row['home'], row['home']), renames.get(row['away'], row['away'])
        _, checks, stops = live.data_checks(h, live.live_frame(rows))
        self.assertEqual(checks['newcomers_per_league']['ENG Premier League'], 5)
        self.assertTrue(any('5 newcomers' in stop for stop in stops))


class RepoTest(unittest.TestCase):
    """Guards and --verify in a temporary git repository."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='live2627_test_')
        self.git('init', '-q')
        os.makedirs(os.path.join(self.root, 'live2627'))
        with open(os.path.join(self.root, live.PREREG), 'w', encoding='utf-8', newline='\n') as handle:
            handle.write('# pre-registration\n')
        self.date = '20261027'
        self.rows = live_rows(history())

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def git(self, *args):
        return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args], cwd=self.root,
                              capture_output=True, text=True, check=True)

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-q', '-m', message)

    def write_snapshot(self):
        live.write_text(live.snapshot_name(self.date), live.snapshot_text(self.date, self.rows), self.root)
        live.write_json(live.manifest_name(self.date), dict(snapshot_date=self.date,
                                                            rows_sha256=live.rows_sha256(self.rows)), self.root)

    def test_scoring_guard_raises_with_uncommitted_or_edited_preregistration(self):
        self.write_snapshot()
        with self.assertRaisesRegex(RuntimeError, 'not committed'):
            live.score(self.date, 'primary', self.root)
        self.commit('live: preregistration')
        live.require_scorable(self.date, self.root)  # committed pre-registration and snapshot: no error
        with open(os.path.join(self.root, live.PREREG), 'a', encoding='utf-8') as handle:
            handle.write('edited\n')
        with self.assertRaisesRegex(RuntimeError, 'differs from the committed'):
            live.score(self.date, 'primary', self.root)
        self.commit('edit')
        with self.assertRaisesRegex(RuntimeError, 'changed after the commit'):
            live.score(self.date, 'primary', self.root)

    def test_scoring_guard_raises_with_uncommitted_snapshot(self):
        self.commit('live: preregistration')
        self.write_snapshot()
        with self.assertRaisesRegex(RuntimeError, 'snapshot_20261027.json is not committed'):
            live.require_scorable(self.date, self.root)

    def test_verify_detects_altered_snapshot(self):
        self.commit('live: preregistration')
        self.write_snapshot()
        self.assertEqual(live.verify(self.root), [])
        path = os.path.join(self.root, live.snapshot_name(self.date))
        with open(path, encoding='utf-8') as handle:
            text = handle.read()
        first = text.index('"goals_home":')
        value = text[first + len('"goals_home":')]
        with open(path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(text[:first] + f'"goals_home":{(int(value) + 1) % 10}' + text[first + len('"goals_home":') + 1:])
        failures = live.verify(self.root)
        self.assertTrue(any('rows sha256 does not match' in failure for failure in failures), failures)


class RuleTest(unittest.TestCase):
    def test_acceptance_rule(self):
        self.assertFalse(live.accepted(0.0))
        self.assertFalse(live.accepted(0.004))
        self.assertTrue(live.accepted(-1e-9))

    def test_bootstrap_reproduces_pinned_interval(self):
        delta = 0.05 * np.sin(np.arange(60)) - 0.004
        ci = live.match_bootstrap({'a': delta, 'b': 2 * delta})
        np.testing.assert_allclose(ci['a'], (-0.012775810329148917, 0.007593838056669123), rtol=0, atol=1e-12)
        # One index matrix is shared by both differences.
        np.testing.assert_allclose(ci['b'], 2 * np.array(ci['a']), rtol=0, atol=1e-12)
        self.assertEqual(live.LEVEL, 0.975)


if __name__ == '__main__':
    unittest.main()
