"""Synthetic, network-free tests for lineup.py (spec F1-F9) and the CSV hand-off to Stage 3."""
import numpy as np
import pandas as pd
import pytest

import lineup
from stage3_detector import load_lineup_adjustments, prepare_lineup_offsets

DEFENCE = ['Goalkeeper', 'Centre-Back', 'Centre-Back', 'Right-Back', 'Left-Back']
ATTACK = ['Defensive Midfield', 'Central Midfield', 'Attacking Midfield',
          'Left Winger', 'Right Winger', 'Centre-Forward']
XI_POSITIONS = DEFENCE + ATTACK


def lineup_rows(game_id, club_id, first_player, positions, kind='starting_lineup'):
    return pd.DataFrame({'game_id': game_id, 'club_id': club_id,
                         'player_id': np.arange(first_player, first_player + len(positions)),
                         'type': kind, 'position': positions})


def links_frame(rows):
    """rows: list of (tm_game_id, home_club_id, away_club_id)."""
    frame = pd.DataFrame(rows, columns=['tm_game_id', 'home_club_id', 'away_club_id'])
    return frame.astype({'tm_game_id': 'Int64', 'home_club_id': 'Int64', 'away_club_id': 'Int64'})


# F1 and F9: last valuation strictly before the match day; mixed datetime units.
@pytest.mark.parametrize('left_unit, right_unit', [('ns', 'us'), ('us', 'ns'), ('ns', 'str')])
def test_valuation_is_last_strictly_before_match_day(left_unit, right_unit):
    starters = pd.DataFrame({'player_id': [1, 2, 3, 4], 'row_id': [0, 0, 0, 0], 'side': 'home',
                             'match_day': pd.to_datetime(['2024-03-10'] * 4).astype(f'datetime64[{left_unit}]')})
    dates = ['2024-03-01', '2024-03-10', '2024-03-15', '2024-03-10', '2024-02-01', '2024-03-09']
    valuations = pd.DataFrame({'player_id': [1, 1, 1, 2, 3, 4],
                               'date': dates if right_unit == 'str'
                               else pd.to_datetime(dates).astype(f'datetime64[{right_unit}]'),
                               'market_value_in_eur': [100, 200, 300, 400, 0, 50]})
    valued = lineup.attach_valuations(starters, valuations)
    # Player 1: same-day (200) and later (300) ignored. Player 2: only a same-day value.
    # Player 3: value <= 0 is missing. Player 4: the day before counts.
    np.testing.assert_array_equal(valued['value'].to_numpy(), [100.0, np.nan, np.nan, 50.0])
    assert list(valued['player_id']) == [1, 2, 3, 4]  # original order restored


def test_valuation_order_restored_with_unsorted_input():
    starters = pd.DataFrame({'player_id': [5, 6, 5], 'row_id': [2, 1, 0], 'side': 'home',
                             'match_day': pd.to_datetime(['2024-05-01', '2023-01-01', '2022-01-01'])})
    valuations = pd.DataFrame({'player_id': [5, 5, 6], 'date': ['2021-06-01', '2024-04-01', '2022-12-01'],
                               'market_value_in_eur': [10, 20, 30]})
    valued = lineup.attach_valuations(starters, valuations)
    np.testing.assert_array_equal(valued['value'].to_numpy(), [20.0, 30.0, 10.0])


# F2: substitutes excluded; a side without exactly 11 distinct starters is missing.
def test_starting_xi_excludes_substitutes_and_requires_eleven():
    game_lineups = pd.concat([
        lineup_rows(10, 1, 100, XI_POSITIONS),
        lineup_rows(10, 1, 200, ['Centre-Forward'] * 3, kind='substitutes'),
        lineup_rows(10, 2, 300, XI_POSITIONS[:10]),                         # 10 starters
        lineup_rows(11, 3, 400, XI_POSITIONS + ['Centre-Forward']),         # 12 starters
        lineup_rows(11, 4, 500, XI_POSITIONS[:10]),
        lineup_rows(11, 4, 509, ['Centre-Forward']),                        # 11 rows, 10 distinct
    ], ignore_index=True)
    links = links_frame([(10, 1, 2), (11, 3, 4), (pd.NA, pd.NA, pd.NA)])
    starters, status = lineup.starting_xi(game_lineups, links)
    assert status.loc[(0, 'home'), 'reason'] == 'ok'
    assert status.loc[(0, 'away'), 'reason'] == 'starter_count'
    assert status.loc[(1, 'home'), 'reason'] == 'starter_count'
    assert status.loc[(1, 'away'), 'reason'] == 'starter_count'
    assert status.loc[(2, 'home'), 'reason'] == 'unmatched'
    assert len(starters) == 11 and set(starters['player_id']) == set(range(100, 111))


# F3: an unmapped or NaN position makes the side missing; casefold/strip still map.
def test_unmapped_or_nan_position_makes_side_missing():
    unmapped = XI_POSITIONS[:10] + ['Libero']
    with_nan = XI_POSITIONS[:10] + [np.nan]
    messy = [' centre-back ', 'midfield'] + XI_POSITIONS[2:]
    game_lineups = pd.concat([lineup_rows(20, 1, 100, unmapped), lineup_rows(20, 2, 200, with_nan),
                              lineup_rows(21, 3, 300, messy), lineup_rows(21, 4, 400, XI_POSITIONS)],
                             ignore_index=True)
    starters, status = lineup.starting_xi(game_lineups, links_frame([(20, 1, 2), (21, 3, 4)]))
    assert status.loc[(0, 'home'), 'reason'] == 'position'
    assert status.loc[(0, 'away'), 'reason'] == 'position'
    assert status.loc[(1, 'home'), 'reason'] == 'ok'
    assert status.loc[(1, 'away'), 'reason'] == 'ok'
    assert list(lineup.map_positions(pd.Series([' centre-back ', 'midfield', 'Libero', np.nan]))[:2]) == \
        ['defence', 'attack']
    assert lineup.map_positions(pd.Series(['Libero', np.nan])).isna().all()


# F4: usual uses strictly earlier fixtures only, needs at least 5, uses at most 10.
def test_usual_uses_previous_fixtures_only():
    n = 12
    sides = pd.DataFrame({'row_id': np.arange(n), 'side': 'home', 'club_id': 7,
                          'attack_value': np.arange(1.0, n + 1), 'defence_value': np.arange(1.0, n + 1) * 10})
    sides = sides.set_index(['row_id', 'side'])
    kickoffs = pd.Series(pd.date_range('2024-01-01', periods=n, freq='7D'), index=np.arange(n))
    usual = lineup.usual_values(sides, kickoffs)
    attack = usual['usual_attack'].to_numpy()
    assert np.isnan(attack[:5]).all()                          # fewer than 5 earlier fixtures
    assert attack[5] == pytest.approx(np.mean([1, 2, 3, 4, 5]))  # the current fixture excluded
    assert attack[11] == pytest.approx(np.mean(range(2, 12)))   # only the previous 10
    assert usual['usual_defence'].to_numpy()[11] == pytest.approx(10 * np.mean(range(2, 12)))


def test_usual_rejects_same_kickoff_twice():
    sides = pd.DataFrame({'row_id': [0, 1], 'side': 'home', 'club_id': 7,
                          'attack_value': [1.0, 2.0], 'defence_value': [1.0, 2.0]}).set_index(['row_id', 'side'])
    kickoffs = pd.Series(pd.to_datetime(['2024-01-01 15:00'] * 2), index=[0, 1])
    with pytest.raises(ValueError):
        lineup.usual_values(sides, kickoffs)


# F5: burn-in drops under 10 prior appearances and rates outside [0.15, 6.0].
def test_burn_in_drops_expected_rows():
    n = 14
    df = pd.DataFrame({'date': pd.date_range('2024-01-01', periods=n, freq='7D'),
                       'team_home': ['A', 'B'] * (n // 2), 'team_away': ['B', 'A'] * (n // 2),
                       'season': '2023-2024'})
    rates = pd.DataFrame({'lambda_home': 1.5, 'mu_away': 1.2}, index=df.index)
    rates.loc[11, 'lambda_home'] = 6.01
    rates.loc[12, 'mu_away'] = 0.149
    rates.loc[13, ['lambda_home', 'mu_away']] = [6.0, 0.15]   # boundaries are inside
    appearances = lineup.prior_appearances(df)
    assert list(appearances['home_prior']) == list(range(n))
    keep = lineup.burn_in_keep(df, rates, appearances, np.ones(n, bool))
    assert list(keep[keep].index) == [10, 13]


# F6: estimation never includes a row dated on or after ESTIMATION_CUTOFF.
def test_estimation_excludes_rows_on_or_after_cutoff():
    test_start = pd.Timestamp('2025-02-01 13:00')
    cutoff = lineup.estimation_cutoff(test_start)
    assert cutoff == pd.Timestamp('2025-01-31 13:00')
    df = pd.DataFrame({'date': [cutoff - pd.Timedelta(minutes=1), cutoff,
                                cutoff + pd.Timedelta(hours=1), test_start],
                       'goals_home': [1, 2, 3, 4], 'goals_away': [0, 1, 2, 3]})
    features = pd.DataFrame({'A_home': 0.1, 'D_home': -0.1, 'A_away': 0.2, 'D_away': -0.2,
                             'n_fallback_home': 0, 'n_fallback_away': 1,
                             'complete_home': True, 'complete_away': True}, index=df.index)
    rates = pd.DataFrame({'lambda_home': 1.5, 'mu_away': 1.2}, index=df.index)
    rows = lineup.estimation_rows(df, features, rates, pd.Series(True, index=df.index), cutoff)
    assert list(rows['match_id']) == [0, 0]
    assert (rows['date'] < cutoff).all()
    assert list(rows['y']) == [1.0, 0.0]
    assert list(rows['A_own']) == [0.1, 0.2] and list(rows['D_opp']) == [-0.2, -0.1]
    assert rows['has_fallback'].all()


def valid_adjustments():
    dates = pd.to_datetime(['2025-02-01 13:00', '2025-02-02 15:00'])
    frame = pd.DataFrame({'date': dates, 'competition': 'ENG Premier League',
                          'team_home': ['A', 'C'], 'team_away': ['B', 'D'],
                          'available_at': dates - pd.Timedelta(minutes=60),
                          'ratings_asof': pd.Timestamp('2025-01-31 13:00'),
                          'home_attack_delta': [0.1, -0.2], 'home_defence_delta': [0.0, 0.3],
                          'away_attack_delta': [0.5, 0.0], 'away_defence_delta': [-0.5, 0.05]},
                         index=[100, 101])
    return frame, pd.Index([99, 100, 101]), pd.Timestamp('2025-02-01 13:00')


# F7: the adjustment asserts fire on bad input.
@pytest.mark.parametrize('corrupt', ['outside_test', 'available_at', 'nan', 'duplicate', 'delta', 'before_start'])
def test_adjustment_asserts_fire(corrupt):
    adjustments, test_index, test_start = valid_adjustments()
    lineup.validate_adjustments(adjustments, test_index, test_start, 2)
    bad = adjustments.copy()
    if corrupt == 'outside_test':
        bad.index = [100, 50]
    elif corrupt == 'available_at':
        bad.loc[101, 'available_at'] = bad.loc[101, 'date']
    elif corrupt == 'nan':
        bad.loc[100, 'home_attack_delta'] = np.nan
    elif corrupt == 'duplicate':
        bad.loc[101, ['team_home', 'team_away', 'date']] = bad.loc[100, ['team_home', 'team_away', 'date']]
        bad.loc[101, 'available_at'] = bad.loc[101, 'date'] - pd.Timedelta(minutes=60)
    elif corrupt == 'delta':
        bad.loc[100, 'away_attack_delta'] = 0.5000001
    elif corrupt == 'before_start':
        bad.loc[100, 'date'] = test_start - pd.Timedelta(minutes=1)
        bad.loc[100, 'available_at'] = bad.loc[100, 'date'] - pd.Timedelta(minutes=60)
    with pytest.raises(ValueError):
        lineup.validate_adjustments(bad, test_index, test_start, 2)


def test_adjustment_row_count_must_match():
    adjustments, test_index, test_start = valid_adjustments()
    with pytest.raises(ValueError):
        lineup.validate_adjustments(adjustments, test_index, test_start, 3)


# F8: the Gate B verdict fails for a wrong sign and for a CI crossing zero.
def test_gate_b_verdict():
    assert lineup.gate_b_verdict(0.10, -0.10, (0.05, 0.15), (-0.15, -0.05))[0]
    wrong_att = lineup.gate_b_verdict(-0.10, -0.10, (-0.15, -0.05), (-0.15, -0.05))
    wrong_def = lineup.gate_b_verdict(0.10, 0.10, (0.05, 0.15), (0.05, 0.15))
    crosses = lineup.gate_b_verdict(0.10, -0.10, (0.05, 0.15), (-0.20, 0.01))
    for passed, reason in (wrong_att, wrong_def, crosses):
        assert not passed and reason
    assert 'c_att' in wrong_att[1] and 'c_def' in wrong_def[1] and 'includes zero' in crosses[1]


def test_placebo_permutes_whole_rows():
    adjustments, _, _ = valid_adjustments()
    placebo = lineup.placebo_adjustments(adjustments, seed=lineup.PLACEBO_SEED)
    rows = {tuple(r) for r in adjustments[lineup.EFFECT_COLUMNS].to_numpy()}
    assert {tuple(r) for r in placebo[lineup.EFFECT_COLUMNS].to_numpy()} == rows
    pd.testing.assert_frame_equal(placebo.drop(columns=lineup.EFFECT_COLUMNS),
                                  adjustments.drop(columns=lineup.EFFECT_COLUMNS))


# The CSV written by lineup.py must land on the same fixtures in prepare_lineup_offsets.
def test_adjustments_csv_round_trip(tmp_path):
    adjustments, _, _ = valid_adjustments()
    matches = pd.DataFrame({'date': pd.to_datetime(['2025-02-01 13:00', '2025-02-01 13:00', '2025-02-02 15:00'])
                            .astype('datetime64[us]'),
                            'competition': 'ENG Premier League',
                            'team_home': ['X', 'A', 'C'], 'team_away': ['Y', 'B', 'D']}, index=[99, 100, 101])
    path = tmp_path / 'adjustments.csv'
    adjustments.to_csv(path, index=False)
    offsets = prepare_lineup_offsets(matches, load_lineup_adjustments(path))
    assert list(offsets.index[offsets['lineup_available']]) == [100, 101]
    np.testing.assert_array_equal(offsets.loc[[100, 101], lineup.EFFECT_COLUMNS].to_numpy(),
                                  adjustments[lineup.EFFECT_COLUMNS].to_numpy())


# EXPLORATORY (post-hoc, attack-only): frozen c_att, defence deltas exactly 0, attack clipped.
def test_attack_only_adjustments():
    dates = pd.to_datetime(['2025-01-20 15:00', '2025-02-01 13:00', '2025-02-02 15:00', '2025-02-03 20:00'])
    df = pd.DataFrame({'date': dates, 'competition': 'ENG Premier League',
                       'team_home': ['A', 'C', 'E', 'G'], 'team_away': ['B', 'D', 'F', 'H']})
    features = pd.DataFrame({'A_home': [0.3, 1.0, -0.4, 0.2], 'A_away': [0.1, -1.0, 0.25, 0.0],
                             'D_home': [0.5, -0.9, 0.7, 0.3], 'D_away': [-0.2, 0.8, -0.6, 0.1],
                             'complete_home': [True, True, True, False],
                             'complete_away': [True, True, True, True]}, index=df.index)
    test_index, test_start = pd.Index([1, 2, 3]), dates[1]
    adjustments = lineup.build_adjustments(df, features, test_index, test_start,
                                           test_start - pd.Timedelta(hours=24), 0.6, 0.0)
    assert list(adjustments.index) == [1, 2]
    np.testing.assert_array_equal(adjustments[['home_defence_delta', 'away_defence_delta']].to_numpy(), 0.0)
    np.testing.assert_allclose(adjustments['home_attack_delta'], [0.5, -0.24])
    np.testing.assert_allclose(adjustments['away_attack_delta'], [-0.5, 0.15])
    lineup.validate_adjustments(adjustments, test_index, test_start, 2)


def test_frozen_attack_coefficient(tmp_path):
    path = tmp_path / 'coefficients.json'
    path.write_text('{"verdict": "FAILED", "c_att": 0.09502689643741223}', encoding='utf-8')
    assert lineup.frozen_attack_coefficient(path) == 0.09502689643741223
    path.write_text('{"verdict": "FAILED", "c_att": 0.1}', encoding='utf-8')
    with pytest.raises(ValueError):
        lineup.frozen_attack_coefficient(path)
