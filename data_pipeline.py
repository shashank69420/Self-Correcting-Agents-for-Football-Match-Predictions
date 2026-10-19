"""Fixture ingestion, cleaning and the 80/20 chronological split."""
import os

import pandas as pd
import penaltyblog as pb

# Local cache of the raw concatenated penaltyblog fixtures (data/ is gitignored).
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
# Pickle, not CSV: it keeps every dtype exactly (datetime64[us] columns, and b365_ch, which
# the scraper returns as text for Eredivisie 2022-23 and as floats elsewhere). Only ever
# loaded from this self-written file; it is tied to the pandas version that wrote it, so
# pass --refresh after upgrading pandas.
RAW_FIXTURES_PATH = os.path.join(PROJECT_DIR, 'data', 'fixtures_raw.pkl')


LEAGUES = ["ENG Premier League", "ESP La Liga", "DEU Bundesliga 1",
           "ITA Serie A", "FRA Ligue 1", "NLD Eredivisie", "PRT Liga 1", "TUR Super Lig",
]
SEASONS = [
    "2019-2020", "2020-2021", "2021-2022",
    "2022-2023", "2023-2024", "2024-2025", "2025-2026"
]


def ingest_and_clean_fixtures(ingest_failures=None, refresh=False):
    leagues = LEAGUES
    seasons = SEASONS

    print("\n[1/4] Scraping/Ingesting match data across 7 seasons...")
    if not refresh and os.path.exists(RAW_FIXTURES_PATH):
        df = pd.read_pickle(RAW_FIXTURES_PATH)
        print(f"  ✓ Ingested all league-seasons from local cache {os.path.relpath(RAW_FIXTURES_PATH, PROJECT_DIR)}"
              " (pass --refresh to re-download)")
    else:
        dataframes = []
        failures_before = len(ingest_failures) if ingest_failures is not None else 0
        for league in leagues:
            for season in seasons:
                try:
                    fb = pb.scrapers.FootballData(league, season)
                    df_temp = fb.get_fixtures()
                    dataframes.append(df_temp)
                    print(f"  ✓ Ingested {league} {season}")
                except Exception as e:
                    if ingest_failures is not None:
                        ingest_failures.append((league, season, repr(e)))
                    print(f"  ✗ Could not ingest {league} {season}: {e}")

        # Concatenate all dataframes efficiently (O(N) memory allocation)
        df = pd.concat(dataframes, ignore_index=True)

        # Cache the raw frame, before dropna / date conversion / sort. A frame missing a
        # league-season would silently become the cache, so only a complete ingest is saved.
        failed = (len(ingest_failures) > failures_before if ingest_failures is not None
                  else len(dataframes) < len(leagues) * len(seasons))
        if failed:
            print("  ! Ingest incomplete; fixture cache not written.")
        else:
            os.makedirs(os.path.dirname(RAW_FIXTURES_PATH), exist_ok=True)
            df.to_pickle(RAW_FIXTURES_PATH)

    # Preprocessing & Data Sanitization
    print("\n[2/4] Sanitizing and chronologically sorting dataset...")
    df = df.dropna(subset=['goals_home', 'goals_away', 'datetime'])
    df['date'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('date').reset_index(drop=True)

    total_rows = len(df)
    null_count = df[['goals_home', 'goals_away', 'team_home', 'team_away']].isnull().sum().sum()

    home_goals_avg = df['goals_home'].mean()
    away_goals_avg = df['goals_away'].mean()

    home_wins = len(df[df['goals_home'] > df['goals_away']])
    away_wins = len(df[df['goals_home'] < df['goals_away']])
    draws = len(df[df['goals_home'] == df['goals_away']])

    print("\n" + "=" * 60)
    print("EMPIRICAL DATASET SUMMARY (FOR SLIDES)")
    print("=" * 60)
    print(f"Total Valid Matches: {total_rows}")
    print(f"Missing Values: {null_count}")
    print(f"Average Home Goals: {home_goals_avg:.3f}")
    print(f"Average Away Goals: {away_goals_avg:.3f}")
    print(f"Home Win Rate: {(home_wins/total_rows)*100:.2f}% ({home_wins} matches)")
    print(f"Draw Rate:     {(draws/total_rows)*100:.2f}% ({draws} matches)")
    print(f"Away Win Rate: {(away_wins/total_rows)*100:.2f}% ({away_wins} matches)")
    return df


def chronological_split(df):
    total_rows = len(df)

    # 80/20 Chronological Train/Test Split
    print("\n[3/4] Performing 80/20 Chronological Split...")
    split_index = int(total_rows * 0.8)
    train_df = df.iloc[:split_index].copy()
    test_df = df.iloc[split_index:].copy()

    print(f"Training Set Cutoff: First {split_index} matches (80%)")
    print(f"Testing Set Size:    Final {len(test_df)} matches (20%)")
    print(f"Training Date Range: {train_df['date'].min().strftime('%Y-%m-%d')} to {train_df['date'].max().strftime('%Y-%m-%d')}")
    print(f"Testing Date Range:  {test_df['date'].min().strftime('%Y-%m-%d')} to {test_df['date'].max().strftime('%Y-%m-%d')}")
    return train_df, test_df
