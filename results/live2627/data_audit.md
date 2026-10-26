# Live 2026-27 data audit (snapshot 1)

Parameters were fixed before 2026-27 data was fetched. Forecasts were recomputed after the matches were played and are not timestamped before kickoff. Team ratings update with each result as it arrives.

Counts and missing shares only: no outcome metric, no forecast. Rules: `live2627/PREREGISTRATION.md`.

- Source: penaltyblog 1.12.3 FootballData(league, '2026-2027').get_fixtures() (football-data.co.uk), the 8 data_pipeline.LEAGUES; fetched 2026-10-26T19:38:02.556135Z.
- Snapshot `results/live2627/snapshot_20261026.json`: 571 rows fetched, 571 completed (goals and datetime present); rows sha256 57df218f259c594149edf2e8d9dc6e6e4af55e12d044c08732b777965d336294.
- Completed rows dated 2026-08-07 19:00 to 2026-10-21 19:00; last H date 2026-05-24 20:00.
- Non-numeric source values written as null: {'goals_home': 0, 'goals_away': 0, 'hst': 0, 'ast': 0, 'avg_ch': 0, 'avg_cd': 0, 'avg_ca': 0}.

## Rows and missing shares per league

SoT missing = share of completed rows with hst or ast missing. Closing avg missing = share of completed rows without a valid avg_ch/avg_cd/avg_ca triple (all three numeric and > 1).

| league | fetched | completed | newcomers | SoT missing | closing avg missing | first | last |
|---|---|---|---|---|---|---|---|
| ENG Premier League | 70 | 70 | 2 | 0.000 | 0.000 | 2026-08-21 | 2026-10-19 |
| ESP La Liga | 89 | 89 | 3 | 0.000 | 0.000 | 2026-08-15 | 2026-10-21 |
| DEU Bundesliga 1 | 54 | 54 | 1 | 0.000 | 0.000 | 2026-08-28 | 2026-10-18 |
| ITA Serie A | 70 | 70 | 0 | 0.000 | 0.000 | 2026-08-22 | 2026-10-19 |
| FRA Ligue 1 | 63 | 63 | 1 | 0.000 | 0.000 | 2026-08-21 | 2026-10-18 |
| NLD Eredivisie | 81 | 81 | 0 | 0.000 | 0.000 | 2026-08-07 | 2026-10-18 |
| PRT Liga 1 | 72 | 72 | 1 | 0.000 | 0.000 | 2026-08-07 | 2026-10-19 |
| TUR Super Lig | 72 | 72 | 3 | 0.000 | 0.000 | 2026-08-14 | 2026-10-19 |

## Newcomers and name audit

Newcomers: teams in L absent from every H row (kept, cold start). Best rapidfuzz WRatio against the H names of the same league, raw and with `utils.default_process`; flagged if either is 88 or more (rows excluded from the test set; names never merged). STOP above 4 newcomers in a league.

| league | team | best_raw | wratio_raw | best_processed | wratio_processed | flagged |
|---|---|---|---|---|---|---|
| ENG Premier League | Coventry | Crystal Palace | 49.1 | Crystal Palace | 49.1 | False |
| ENG Premier League | Hull | Aston Villa | 51.4 | Aston Villa | 51.4 | False |
| ESP La Liga | La Coruna | Girona | 54.0 | Barcelona | 55.6 | False |
| ESP La Liga | Malaga | Mallorca | 57.1 | Mallorca | 57.1 | False |
| ESP La Liga | Santander | Granada | 50.0 | Ath Madrid | 52.6 | False |
| DEU Bundesliga 1 | Elversberg | Wolfsburg | 52.6 | Leverkusen | 60.0 | False |
| FRA Ligue 1 | Le Mans | Lens | 72.7 | Lens | 72.7 | False |
| PRT Liga 1 | Academico Viseu | Arouca | 60.0 | AVS | 60.0 | False |
| TUR Super Lig | Amedspor | Umraniyespor | 69.2 | Umraniyespor | 69.2 | False |
| TUR Super Lig | Corum | Bodrumspor | 72.0 | Bodrumspor | 72.0 | False |
| TUR Super Lig | Erzurumspor | Bodrumspor | 66.7 | Bodrumspor | 66.7 | False |

- Newcomers: 11.
- WRatio rule (pre-registered): flagged 0 at WRatio >= 88.
- Alias check (post-hoc stricter reading, below): 1 flagged, including Erzurumspor, which the WRatio rule missed.
  Erzurumspor is the only one.

## Alias check (post-hoc stricter reading, 2026-10-27)

Added after the snapshot was written and before any score; DECISIONS.md, 2026-10-27. Everything else in this file is
as `--snapshot` wrote it. Reproduce with `python -X utf8 live2627.py --alias-check` (read only).

Rule: a newcomer is an alias if its Transfermarkt club_id appears in H under another name. H names get their club_id
from the lineup audit's fixture link (`lineup.link_fixtures`, unchanged; every H name has exactly one club_id). A
newcomer's own club_id(s) are the clubs in `data/clubs.csv.gz` (name or club_code) or `data/games.csv.gz` (home or away
club name) whose name contains the newcomer's name (default_process, accents removed). Top 3 H names are taken across
all leagues by WRatio. A flagged alias is excluded from the test set like a WRatio flag. No names are merged in any
data.

| league | newcomer | top 3 H names, raw (WRatio, club_id) | top 3 H names, processed (WRatio, club_id) | own club_id(s) | own club_id in H | decision |
|---|---|---|---|---|---|---|
| ENG Premier League | Coventry | Como 60.0 (1047); Inter 60.0 (46); PSV Eindhoven 60.0 (383) | same as raw | 990 Coventry City | no | not an alias |
| ENG Premier League | Hull | Huesca 60.0 (5358); Aston Villa 51.4 (405); Fulham 51.4 (931) | Huesca 60.0 (5358); Aston Villa 51.4 (405); Bochum 51.4 (80) | 3008 Hull City; 12335 Solihull Moors | no | not an alias |
| ESP La Liga | La Coruna | Como 57.0 (1047); Fortuna Dusseldorf 57.0 (38); Arouca 54.0 (8024) | Nacional 58.8 (982); Altay 57.0 (2375); Como 57.0 (1047) | 897 Deportivo de La Coruña | no | not an alias |
| ESP La Liga | Malaga | Yeni Malatyaspor 68.4 (19789); Galatasaray 60.0 (141); Atalanta 57.1 (800) | Yeni Malatyaspor 68.4 (19789); AZ Alkmaar 60.0 (1090); Alanyaspor 60.0 (11282) | 1084 Málaga CF | no | not an alias |
| ESP La Liga | Santander | Inter 60.0 (46); Spal 60.0 (2722); Salernitana 60.0 (380) | Angers 65.5 (1420); Inter 60.0 (46); Nantes 60.0 (995) | 630 Racing Santander; 103271 CD Monte Santander | no | not an alias |
| DEU Bundesliga 1 | Elversberg | Aves 67.5 (3336); Alaves 60.0 (1108); Elche 60.0 (1531) | same as raw | 64 SV 07 Elversberg | no | not an alias |
| FRA Ligue 1 | Le Mans | Lens 72.7 (826); Leganes 71.4 (1244); Levante 57.1 (3368) | Lens 72.7 (826); Leganes 71.4 (1244); AVS 60.0 (110302) | none in the tables | n/a | not decidable by club_id; not flagged |
| PRT Liga 1 | Academico Viseu | Arouca 60.0 (8024); Vitesse 60.0 (499); Alverca 54.0 (2521) | AVS 60.0 (110302); Arouca 60.0 (8024); Cadiz 60.0 (2687) | 7788 Académico Viseu FC | no | not an alias |
| TUR Super Lig | Amedspor | Umraniyespor 69.2 (24245); Pendikspor 66.7 (3209); Rizespor 62.5 (126) | Umraniyespor 69.2 (24245); Yeni Malatyaspor 69.2 (19789); Porto 67.5 (720) | none in the tables | n/a | not decidable by club_id; not flagged |
| TUR Super Lig | Corum | Bodrumspor 72.0 (44006); Como 66.7 (1047); Erzurum BB 64.1 (39722) | same as raw | none in the tables | n/a | not decidable by club_id; not flagged |
| TUR Super Lig | Erzurumspor | Bodrumspor 66.7 (44006); Erzurum BB 66.7 (39722); Eyupspor 63.2 (7160) | Porto 67.5 (720); Bodrumspor 66.7 (44006); Erzurum BB 66.7 (39722) | 39722 Erzurumspor FK (club_code buyuksehir-belediye-erzurumspor) | yes: Erzurum BB (39722) | **ALIAS, flagged** |

Erzurumspor evidence: `clubs.csv.gz` club 39722 is "Erzurumspor FK", club_code "buyuksehir-belediye-erzurumspor",
domestic competition TR1, last_season 2020; the H name "Erzurum BB" (TUR Super Lig 2020-2021, 40 H rows) links to
club 39722 in all 40 and to no other club_id. Its
best same-league WRatio was 66.7 (Bodrumspor), below 88, so the pre-registered rule did not flag it.

Rows excluded from the primary test set for a club_id alias: 8 in total.

| league | rows excluded (alias) |
|---|---|
| ENG Premier League | 0 |
| ESP La Liga | 0 |
| DEU Bundesliga 1 | 0 |
| ITA Serie A | 0 |
| FRA Ligue 1 | 0 |
| NLD Eredivisie | 0 |
| PRT Liga 1 | 0 |
| TUR Super Lig | 8 |

- TUR Super Lig: Amedspor v Erzurumspor, 2026-08-16 19:30
- TUR Super Lig: Erzurumspor v Galatasaray, 2026-08-21 19:30
- TUR Super Lig: Genclerbirligi v Erzurumspor, 2026-08-28 19:30
- TUR Super Lig: Erzurumspor v Konyaspor, 2026-09-05 15:00
- TUR Super Lig: Besiktas v Erzurumspor, 2026-09-11 18:00
- TUR Super Lig: Erzurumspor v Samsunspor, 2026-09-20 15:00
- TUR Super Lig: Alanyaspor v Erzurumspor, 2026-10-10 14:00
- TUR Super Lig: Erzurumspor v Eyupspor, 2026-10-17 11:30

## Checks

- Duplicate (league, datetime, home, away) rows: 0.
- Duplicate (league, season, home, away) pairs: 0.
- Team-days with two matches: 0.
- Names with leading or trailing spaces: none.
- Overlap with the forward log (6 logged rows): 0 completed L rows, excluded from the test set.
- Columns present in the fetch: 119; SoT columns ['hst', 'ast']; closing average columns ['avg_ch', 'avg_cd', 'avg_ca'].
