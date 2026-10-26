"""Network-free tests for forward_logger.py (T1 uses the fixture cache; the rest are synthetic).

Run: python -X utf8 -m unittest tests.test_forward -v
"""
import datetime as dt
import json
import os
import subprocess
import tempfile
import unittest

import numpy as np
import pandas as pd

import exp_model
import forward_logger as fl
import metrics

UTC = dt.UTC
NOW = dt.datetime(2026, 11, 1, 12, 0, tzinfo=UTC)   # 1 November: UK on GMT, so UK local = UTC
LEAGUE = 'ENG Premier League'
HEAD = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=fl.PROJECT_DIR, capture_output=True,
                      text=True).stdout.strip()


def synthetic_raw(season, teams, start, seed=0):
    """A double round robin with penaltyblog's raw columns (naive UK-local datetime)."""
    rng = np.random.default_rng(seed)
    rows, kickoff = [], pd.Timestamp(start)
    for home in teams:
        for away in teams:
            if home != away:
                rows.append(dict(competition=LEAGUE, season=season, datetime=kickoff, team_home=home,
                                 team_away=away, goals_home=int(rng.poisson(1.5)), goals_away=int(rng.poisson(1.1))))
                kickoff += pd.Timedelta(days=3)
    return pd.DataFrame(rows)


def synthetic_history():
    cache = synthetic_raw('2025-2026', ['A', 'B', 'C', 'D'], '2025-08-16 15:00')
    season = synthetic_raw(fl.SEASON, ['A', 'B', 'C', 'New'], '2026-08-15 15:00', seed=1)
    return fl.build_history(cache, season)


def fixtures(*matches):
    """matches: (date dd/mm/yyyy, time, home, away); a Div code may be given as a fifth item."""
    records = [dict(Div=(m[4] if len(m) > 4 else 'E0'), Date=m[0], Time=m[1], HomeTeam=m[2], AwayTeam=m[3],
                    Referee='', B365H='2.10', B365D='3.40', B365A='', AvgH='2.05') for m in matches]
    return pd.DataFrame(records, dtype=str)


PROVENANCE = dict(source_url=fl.FIXTURES_URL, source_fetched_at_utc='2026-11-01T11:59:00Z', code_commit=HEAD,
                  code_dirty=False, params_sha256='0' * 64)


class LogCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = synthetic_history()
        cls.models = fl.frozen_models()[0]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.tmp.name, 'forward', 'predictions.jsonl')

    def tearDown(self):
        self.tmp.cleanup()

    def run_log(self, frame, now=NOW):
        return fl.log_fixtures(frame, self.history, self.models, fl.HOME_ADV, PROVENANCE, self.log, now=now)

    def lines(self):
        with open(self.log, 'rb') as handle:
            return handle.read().splitlines(keepends=True)

    def write_lines(self, lines):
        with open(self.log, 'wb') as handle:
            handle.write(b''.join(lines))


class ReplayTest(unittest.TestCase):
    """T1: a forecast from the post-history state equals run_filter's own pre-match forecast for that row."""

    def test_replay_matches_run_filter(self):
        df = fl.clean(fl.load_cache())
        seen, eligible = set(), []
        for position, row in enumerate(df.itertuples()):
            if row.season in ('2023-2024', '2024-2025', '2025-2026') and {row.team_home, row.team_away} <= seen:
                eligible.append((row.season, position))
            seen.update((row.team_home, row.team_away))
        chosen = []
        for season in ('2023-2024', '2024-2025', '2025-2026'):
            positions = [p for s, p in eligible if s == season]
            chosen += [positions[i] for i in np.linspace(0, len(positions) - 1, 4).round().astype(int)]
        self.assertGreaterEqual(len(chosen), 10)
        models = fl.frozen_models()[0]
        worst = 0.0
        for name, params in models.items():
            full = exp_model.run_filter(df, params, fl.HOME_ADV)
            for position in chosen:
                states, _ = fl.snapshot_states(df.iloc[:position], params, fl.HOME_ADV)
                row = df.iloc[position]
                got = fl.forecast_fixture(states, row.team_home, row.team_away, params, fl.HOME_ADV)
                want = full.iloc[position]
                self.assertEqual((want.team_home, want.team_away), (row.team_home, row.team_away))
                diffs = [abs(got[a] - want[b]) for a, b in (('home', 'pred_home_win'), ('draw', 'pred_draw'),
                                                            ('away', 'pred_away_win'), ('lambda', 'lambda_home'),
                                                            ('mu', 'mu_away'))]
                worst = max(worst, *diffs)
        print(f'\nT1 replay: {len(chosen)} rows x {len(models)} models, max abs difference {worst!r}')
        self.assertLessEqual(worst, 1e-12)

    def test_home_adv_recomputes_from_cache(self):
        self.assertLessEqual(abs(fl.check_home_adv(fl.load_cache()) - fl.HOME_ADV), 1e-12)


class RerunTest(LogCase):
    def test_second_run_adds_no_rows(self):
        """T2."""
        frame = fixtures(('02/11/2026', '15:00', 'A', 'B'), ('02/11/2026', '17:30', 'C', 'New'))
        first, _, _ = self.run_log(frame)
        before = self.lines()
        second, refused, _ = self.run_log(frame, now=NOW + dt.timedelta(minutes=5))
        self.assertEqual((len(first), len(second)), (2, 0))
        self.assertEqual([reason for reason, _ in refused], ['already logged'] * 2)
        self.assertEqual(self.lines(), before)


class RefusalTest(LogCase):
    def test_lead_time_and_missing_time(self):
        """T3: past kickoff, under 3h, exactly 3h and missing time refused; 3h01m accepted."""
        frame = fixtures(('01/11/2026', '11:00', 'A', 'B'), ('01/11/2026', '14:30', 'C', 'A'),
                         ('01/11/2026', '15:00', 'B', 'C'), ('01/11/2026', '', 'A', 'C'),
                         ('01/11/2026', '15:01', 'C', 'B'))
        rows, refused, _ = self.run_log(frame)
        self.assertEqual([reason for reason, _ in refused],
                         ['kickoff passed', 'under 3 hours', 'under 3 hours', 'missing time'])
        self.assertEqual([(r['home'], r['away'], r['kickoff_utc']) for r in rows],
                         [('C', 'B', '2026-11-01T15:01:00Z')])

    def test_unknown_team_refused_and_listed(self):
        """T4: absent everywhere is refused by name; a 2026-2027-only newcomer is accepted."""
        frame = fixtures(('02/11/2026', '15:00', 'Nowhere FC', 'A'), ('02/11/2026', '15:00', 'New', 'D'),
                         ('02/11/2026', '15:00', 'B', 'Elsewhere'), ('02/11/2026', '15:00', 'X', 'Y', 'B1'))
        rows, refused, ignored = self.run_log(frame)
        self.assertEqual([r['home'] for r in rows], ['New'])
        self.assertEqual([reason for reason, _ in refused],
                         ['unknown team: Nowhere FC', 'unknown team: Elsewhere'])
        self.assertEqual(ignored, 1)


class TimeZoneTest(unittest.TestCase):
    def test_uk_local_to_utc(self):
        """T5: winter (GMT) and summer (BST) dates; clock-change ambiguity refused."""
        self.assertEqual(fl.parse_kickoff('15/01/2027', '15:00'), dt.datetime(2027, 1, 15, 15, 0, tzinfo=UTC))
        self.assertEqual(fl.parse_kickoff('15/08/2026', '15:00'), dt.datetime(2026, 8, 15, 14, 0, tzinfo=UTC))
        self.assertEqual(fl.parse_kickoff('15/08/26', '20:00'), dt.datetime(2026, 8, 15, 19, 0, tzinfo=UTC))
        with self.assertRaises(ValueError):
            fl.parse_kickoff('25/10/2026', '01:30')   # occurs twice
        with self.assertRaises(ValueError):
            fl.parse_kickoff('28/03/2027', '01:30')   # does not occur


class VerifyTest(LogCase):
    def setUp(self):
        super().setUp()
        self.run_log(fixtures(('02/11/2026', '15:00', 'A', 'B'), ('02/11/2026', '17:30', 'C', 'New'),
                              ('03/11/2026', '19:45', 'B', 'C')))
        self.assertEqual(fl.verify_log(self.log), [])

    def test_edited_field_detected(self):
        """T6."""
        lines = self.lines()
        row = json.loads(lines[1])
        row['p1_home'] += 0.01
        self.write_lines([lines[0], (fl.canonical(row) + '\n').encode(), lines[2]])
        self.assertTrue(any('row_hash' in f for f in fl.verify_log(self.log)))

    def test_deleted_row_detected(self):
        lines = self.lines()
        self.write_lines([lines[0], lines[2]])
        self.assertTrue(any('prev_hash' in f for f in fl.verify_log(self.log)))

    def test_reordered_rows_detected(self):
        lines = self.lines()
        self.write_lines([lines[1], lines[0], lines[2]])
        self.assertNotEqual(fl.verify_log(self.log), [])

    def test_valid_appends_pass(self):
        rows, _, _ = self.run_log(fixtures(('04/11/2026', '19:00', 'A', 'C')), now=NOW + dt.timedelta(hours=1))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(self.lines()), 4)
        self.assertEqual(fl.verify_log(self.log), [])

    def test_lead_time_and_commit_checked(self):
        lines = self.lines()
        accepted = [dict(league=LEAGUE, home='D', away='A', kickoff=NOW + dt.timedelta(hours=2), odds={})]
        states = {name: fl.snapshot_states(self.history, self.models[name], fl.HOME_ADV)[0] for name in fl.MODELS}
        context = dict(PROVENANCE, code_commit='f' * 40, history_through='2026-11-01T00:00:00Z', n_history_rows=1)
        rows = fl.build_rows(accepted, states, self.models, fl.HOME_ADV, context,
                             json.loads(lines[-1])['row_hash'], NOW)
        fl.append_rows(self.log, rows)
        failures = fl.verify_log(self.log)
        self.assertTrue(any('3 hours' in f for f in failures))
        self.assertTrue(any('not found in git' in f for f in failures))


class RescheduleTest(LogCase):
    def test_reschedule_keeps_first_forecast(self):
        """T7."""
        first, _, _ = self.run_log(fixtures(('02/11/2026', '15:00', 'A', 'B')))
        later, refused, _ = self.run_log(fixtures(('09/11/2026', '20:00', 'A', 'B')), now=NOW + dt.timedelta(days=1))
        self.assertEqual((len(first), len(later)), (1, 0))
        self.assertEqual(refused[0][0], 'already logged')
        rows = fl.read_log(self.log)
        self.assertEqual([r['kickoff_utc'] for r in rows], ['2026-11-02T15:00:00Z'])
        self.assertEqual(rows[0]['p1_home'], first[0]['p1_home'])


def scored_row(home, away, kickoff, p1, base):
    row = dict(league=LEAGUE, season=fl.SEASON, home=home, away=away, kickoff_utc=kickoff,
               fixture_id=f'{LEAGUE}|{kickoff}|{home}|{away}')
    for name, probs in (('p1', p1), ('base', base)):
        row.update({f'{name}_home': probs[0], f'{name}_draw': probs[1], f'{name}_away': probs[2]})
    return row


def results(*matches):
    """matches: (home, away, UK-local datetime, goals_home, goals_away)."""
    return pd.DataFrame([dict(competition=LEAGUE, season=fl.SEASON, team_home=h, team_away=a,
                              date=pd.Timestamp(when), goals_home=gh, goals_away=ga)
                         for h, a, when, gh, ga in matches])


class ScoreTest(unittest.TestCase):
    def test_hand_computed_scores_and_statuses(self):
        """T8."""
        rows = [scored_row('A', 'B', '2026-10-31T15:00:00Z', (0.5, 0.3, 0.2), (0.4, 0.3, 0.3)),   # home win
                scored_row('C', 'D', '2026-10-31T15:00:00Z', (0.2, 0.3, 0.5), (0.25, 0.35, 0.4)),  # draw
                scored_row('E', 'F', '2026-10-28T19:00:00Z', (0.4, 0.3, 0.3), (0.4, 0.3, 0.3)),    # postponed
                scored_row('G', 'H', '2026-10-20T19:00:00Z', (0.4, 0.3, 0.3), (0.4, 0.3, 0.3)),    # unresolved
                scored_row('I', 'J', '2026-10-30T19:00:00Z', (0.4, 0.3, 0.3), (0.4, 0.3, 0.3))]    # too early
        played = results(('A', 'B', '2026-10-31 15:00', 2, 1), ('C', 'D', '2026-11-01 14:00', 1, 1),
                         ('I', 'J', '2026-10-25 19:00', 0, 3))
        with tempfile.TemporaryDirectory() as tmp:
            log, report = os.path.join(tmp, 'predictions.jsonl'), os.path.join(tmp, 'score_report.md')
            fl.append_rows(log, rows)
            with open(log, 'rb') as handle:
                before = handle.read()
            text = fl.score_log(log, report, played, NOW, now=NOW)
            with open(log, 'rb') as handle:
                self.assertEqual(handle.read(), before)
            with open(report, encoding='utf-8') as handle:
                self.assertEqual(handle.read(), text)
        summary = fl.score_summary(rows, played, NOW)
        self.assertEqual({k: summary[k] for k in ('logged', 'scored', 'pending', 'unresolved')},
                         dict(logged=5, scored=2, pending=2, unresolved=1))
        self.assertEqual(summary['unresolved_ids'], [rows[3]['fixture_id']])
        p1_loss = (-np.log(0.5) - np.log(0.3)) / 2
        base_loss = (-np.log(0.4) - np.log(0.35)) / 2
        p1_rps = (0.5 * (0.5 ** 2 + 0.2 ** 2) + 0.5 * (0.2 ** 2 + 0.5 ** 2)) / 2
        base_rps = (0.5 * (0.6 ** 2 + 0.3 ** 2) + 0.5 * (0.25 ** 2 + 0.4 ** 2)) / 2
        self.assertAlmostEqual(summary['metrics']['p1']['LogLoss'], p1_loss, places=12)
        self.assertAlmostEqual(summary['metrics']['base']['LogLoss'], base_loss, places=12)
        self.assertAlmostEqual(summary['metrics']['p1']['RPS'], p1_rps, places=12)
        self.assertAlmostEqual(summary['metrics']['base']['RPS'], base_rps, places=12)
        self.assertAlmostEqual(summary['delta'], p1_loss - base_loss, places=12)
        self.assertIsNone(summary['ci'])
        self.assertIn('DESCRIPTIVE ONLY', text)

    def test_ci_from_600_scored(self):
        rng = np.random.default_rng(3)
        kickoffs = pd.date_range('2026-08-15 15:00', periods=600, freq='8h')
        rows, played = [], []
        for number, kickoff in enumerate(kickoffs):
            p1 = rng.dirichlet([2, 1, 1])
            rows.append(scored_row(f'H{number}', f'A{number}', kickoff.strftime('%Y-%m-%dT%H:%M:%SZ'),
                                   tuple(p1), (0.45, 0.27, 0.28)))
            played.append((f'H{number}', f'A{number}', kickoff, int(rng.poisson(1.4)), int(rng.poisson(1.1))))
        self.assertIsNone(fl.score_summary(rows[:599], results(*played), NOW)['ci'])
        summary = fl.score_summary(rows, results(*played), NOW)
        self.assertEqual(summary['scored'], 600)
        self.assertEqual(len(summary['ci']), 2)


# Fixed input for the three CI tests: 600 deltas over 200 days (about 29 calendar weeks).
CI_DELTA = np.random.default_rng(3).normal(size=600)
CI_DATES = pd.Series(pd.date_range('2026-08-15 15:00', periods=600, freq='8h'))
CI_WEEKS = CI_DATES.dt.to_period('W').astype(str).to_numpy()


class SeededCiTest(unittest.TestCase):
    def test_same_algorithm_as_metrics_helper(self):
        """(i) With the helper's own seed the two functions agree, so the algorithm is the same."""
        ours = fl.paired_week_block_ci_seeded(CI_DELTA, CI_WEEKS, 20260922)
        np.testing.assert_allclose(ours, metrics.paired_week_block_ci(CI_DELTA, CI_DATES), rtol=0, atol=1e-12)

    def test_seed_is_used(self):
        """(ii) Different seeds give different intervals on the same input."""
        a = fl.paired_week_block_ci_seeded(CI_DELTA, CI_WEEKS, 20261027)
        b = fl.paired_week_block_ci_seeded(CI_DELTA, CI_WEEKS, 20260922)
        self.assertFalse(np.allclose(a, b, rtol=0, atol=1e-6))

    def test_pinned_value_for_preregistered_seed(self):
        """(iii) The interval for seed 20261027 (the score report's seed) is pinned."""
        np.testing.assert_allclose(fl.paired_week_block_ci_seeded(CI_DELTA, CI_WEEKS, fl.CI_SEED),
                                   [-0.008326419307179747, 0.14718068232151577], rtol=0, atol=1e-12)
        self.assertEqual(fl.CI_SEED, 20261027)


class CliTest(unittest.TestCase):
    def test_no_option_sets_the_clock(self):
        """T9: the only options are --score, --verify and help."""
        options = {opt for action in fl.build_parser()._actions for opt in action.option_strings}
        self.assertEqual(options, {'-h', '--help', '--score', '--verify'})


if __name__ == '__main__':
    unittest.main()
