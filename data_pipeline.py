"""Fixture ingestion, cleaning and the 80/20 chronological split."""
import pandas as pd
import penaltyblog as pb


def ingest_and_clean_fixtures():
    leagues = ["ENG Premier League", "ESP La Liga", "DEU Bundesliga 1",
               "ITA Serie A", "FRA Ligue 1", "NLD Eredivisie", "PRT Liga 1", "TUR Super Lig",
    ]
    seasons = [
        "2019-2020", "2020-2021", "2021-2022",
        "2022-2023", "2023-2024", "2024-2025", "2025-2026"
    ]

    dataframes = []
    print("\n[1/4] Scraping/Ingesting match data across 7 seasons...")
    for league in leagues:
        for season in seasons:
            try:
                fb = pb.scrapers.FootballData(league, season)
                df_temp = fb.get_fixtures()
                dataframes.append(df_temp)
                print(f"  ✓ Ingested {league} {season}")
            except Exception as e:
                print(f"  ✗ Could not ingest {league} {season}: {e}")

    # Concatenate all dataframes efficiently (O(N) memory allocation)
    df = pd.concat(dataframes, ignore_index=True)

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
