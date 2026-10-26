# P2 fresh data audit (2014-2015 to 2018-2019)

Counts and missing shares only: no outcome metric, no forecast. Source: penaltyblog FootballData (football-data.co.uk), fetched fresh; raw cache `data/fixtures_pre2019.pkl` (not committed).

- League-seasons requested: 40; fetched: 40; not fetchable: 0 (0.0%; STOP above 10%).
- Raw rows: 13720; clean rows (data_pipeline cleaning + datetime fallback): 13720; 2014-2015 burn-in rows: 2744; scored rows (2015-2016 to 2018-2019): 10976.
- Date range: 2014-08-08 to 2019-05-26. Seasons present: ['2014-2015', '2015-2016', '2016-2017', '2017-2018', '2018-2019'].
- League-seasons using the pre-registered datetime = Date fallback (no Time column): 40 of 40.

## Rows and missing shares per league-season

SoT missing = share of rows with hst or ast missing. Snapshot missing = share of rows without a valid snapshot triple (all three odds numeric and > 1). Closing columns are evaluation-only.

| league season | raw rows | clean rows | datetime = Date | SoT missing | snapshot cols | snapshot missing | closing average missing | Pinnacle closing missing |
|---|---|---|---|---|---|---|---|---|
| ENG Premier League 2014-2015 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| ENG Premier League 2015-2016 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| ENG Premier League 2016-2017 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| ENG Premier League 2017-2018 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| ENG Premier League 2018-2019 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| ESP La Liga 2014-2015 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| ESP La Liga 2015-2016 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| ESP La Liga 2016-2017 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| ESP La Liga 2017-2018 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.003 |
| ESP La Liga 2018-2019 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| DEU Bundesliga 1 2014-2015 | 306 | 306 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| DEU Bundesliga 1 2015-2016 | 306 | 306 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| DEU Bundesliga 1 2016-2017 | 306 | 306 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| DEU Bundesliga 1 2017-2018 | 306 | 306 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| DEU Bundesliga 1 2018-2019 | 306 | 306 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.003 |
| ITA Serie A 2014-2015 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| ITA Serie A 2015-2016 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| ITA Serie A 2016-2017 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| ITA Serie A 2017-2018 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| ITA Serie A 2018-2019 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| FRA Ligue 1 2014-2015 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| FRA Ligue 1 2015-2016 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| FRA Ligue 1 2016-2017 | 380 | 380 | True | 0.003 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| FRA Ligue 1 2017-2018 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| FRA Ligue 1 2018-2019 | 380 | 380 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| NLD Eredivisie 2014-2015 | 306 | 306 | True | 1.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.003 |
| NLD Eredivisie 2015-2016 | 306 | 306 | True | 1.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| NLD Eredivisie 2016-2017 | 306 | 306 | True | 1.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| NLD Eredivisie 2017-2018 | 306 | 306 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.010 |
| NLD Eredivisie 2018-2019 | 306 | 306 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| PRT Liga 1 2014-2015 | 306 | 306 | True | 1.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.003 |
| PRT Liga 1 2015-2016 | 306 | 306 | True | 1.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| PRT Liga 1 2016-2017 | 306 | 306 | True | 1.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| PRT Liga 1 2017-2018 | 306 | 306 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.007 |
| PRT Liga 1 2018-2019 | 306 | 306 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| TUR Super Lig 2014-2015 | 306 | 306 | True | 1.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.003 |
| TUR Super Lig 2015-2016 | 306 | 306 | True | 1.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |
| TUR Super Lig 2016-2017 | 306 | 306 | True | 1.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.003 |
| TUR Super Lig 2017-2018 | 306 | 306 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.010 |
| TUR Super Lig 2018-2019 | 306 | 306 | True | 0.000 | bb_av_h/bb_av_d/bb_av_a | 0.000 | 1.000 | 0.000 |

## Column names

- Shots on target: `hst`, `ast` (home, away).
- Snapshot triple on F: bb_av_h/bb_av_d/bb_av_a.
- Non-closing odds-like columns: `b365_h`, `b365_d`, `b365_a`, `bwh`, `bwd`, `bwa`, `iwh`, `iwd`, `iwa`, `lbh`, `lbd`, `lba`, `psh`, `psd`, `psa`, `whh`, `whd`, `wha`, `sjh`, `sjd`, `sja`, `vch`, `vcd`, `vca`, `bb1_x2`, `bb_mx_h`, `bb_av_h`, `bb_mx_d`, `bb_av_d`, `bb_mx_a`, `bb_av_a`, `bb_ou`, `bb_mx>2.5`, `bb_av>2.5`, `bb_mx<2.5`, `bb_av<2.5`, `bb_ah`, `bb_a_hh`, `bb_mx_ahh`, `bb_av_ahh`, `bb_mx_aha`, `bb_av_aha`.
- Closing odds-like columns: `psch`, `pscd`, `psca`.

## Team names

- Unique teams per league: {'DEU Bundesliga 1': 23, 'ENG Premier League': 29, 'ESP La Liga': 29, 'FRA Ligue 1': 28, 'ITA Serie A': 27, 'NLD Eredivisie': 25, 'PRT Liga 1': 25, 'TUR Super Lig': 27}.
- Teams per league-season: min 18, max 20.
- Teams appearing in more than one league: none.
- Names with leading or trailing spaces: none.
- Team-days with two matches (would break same-day ordering): 0.
