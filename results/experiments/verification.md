# Verification: odds timing and the P1 headline

Verification only. No model code was changed. All metrics are on DEV and VAL rows, which are selection-period,
retrospective and not out-of-sample. TEST rows are not scored (the `exp_harness.assert_no_test` guard is applied
in every metric call). Items 2–4 were produced by the script in the appendix, run on 2026-10-25.

## 1. Football-data notes: when were the non-closing odds collected?

Source: https://www.football-data.co.uk/notes.txt. This is the file linked as `HREF="notes.txt"` on
https://www.football-data.co.uk/data.php. Read on 2026-10-25 at about 08:09 UTC with curl (7,686 bytes; the http and
https copies are identical). The earlier attempts on the same day were blocked by the network filter.

Verbatim quotes:

> "Betting odds for weekend games are collected Friday afternoons, and on Tuesday afternoons for midweek games."

> "The following key to betting odds data is described below. These are for pre-closing odds. For the closing odds, as below but with an additional "C" character following the bookmaker abbreviation/Max/Avg (e.g. B365CH = closing Bet365 home win odds)."

Verdict: **timing is stated, as a collection schedule.** The non-closing columns were collected on Friday afternoon
for weekend games and on Tuesday afternoon for midweek games. The data has no timestamp per row, so for any single
match the gap between collection and kickoff cannot be checked. The schedule also does not say how Friday-evening,
Monday or Tuesday-evening fixtures were handled. For most fixtures, collection should come well before T-60.

The audit's "C-suffix = closing" rule is confirmed. One label is corrected: the notes define `CLH/CLD/CLA` as
**Coral**, not Coolbet as `odds_audit.md` and an `exp_harness.py` comment state. The coverage numbers are unaffected
(those columns are 100% missing on non-TEST rows). The existing files were not edited. `BFH/BFD/BFA` = Betfair and
`BFDH/BFDD/BFDA` = Betfred are confirmed.

## 2. candidate_p1.json

```json
{
  "candidate": "P1",
  "accepted_experiments": [
    "E1",
    "E3",
    "E5"
  ],
  "params": {
    "process_noise": 0.005,
    "initial_var": 0.3,
    "cold_defence": 0.3,
    "clip_rates": true,
    "rho": -0.04
  },
  "calibration": null,
  "note": "Overrides of exp_model.DEFAULT_PARAMS; home_adv stays compute_home_adv(train_df, test_df)."
}
```

### Holm table (all six experiments)

p_one_sided = (1 + #{bootstrap mean delta >= 0}) / 2001; Holm step-down over E1-E6. Acceptance used the locked rule, not these p-values.

| experiment | chosen | mean_delta_logloss | ci_rows | ci99_low | ci99_high | p_one_sided | p_holm | verdict |
|---|---|---|---|---|---|---|---|---|
| E1 | {"process_noise": 0.005, "initial_var": 0.3} | -0.015803 | DEV+VAL | -0.020189 | -0.012334 | 0.000500 | 0.002999 | ACCEPTED |
| E2 | {"drift_per_day": 0.0, "season_var": 0.0} | 0.000000 | DEV+VAL | 0.000000 | 0.000000 | 1.000000 | 1.000000 | REJECTED |
| E3 | {"cold_attack": 0.0, "cold_defence": 0.3, "clip_rates": true} | -0.000768 | DEV+VAL | -0.001715 | -0.000099 | 0.001499 | 0.005997 | ACCEPTED |
| E4 | {"league_k": null} | 0.000000 | DEV+VAL | 0.000000 | 0.000000 | 1.000000 | 1.000000 | REJECTED |
| E5 | {"rho": -0.04} | -0.000552 | DEV+VAL | -0.000999 | -0.000116 | 0.000500 | 0.002999 | ACCEPTED |
| E6 | {"temperature": 1.2551125450691194, "bias": [0.0464618750007404, -0.03708219747085956, -0.009379677529880844]} | -0.002784 | VAL | -0.006639 | 0.001068 | 0.024988 | 0.074963 | REJECTED |

## 3. Closing market vs baseline and P1 (rows with valid avg_ch/avg_cd/avg_ca)

Market = normalised 1/odds of the closing market average; evaluation only (later information than T-60). Gap closed = (baseline - P1) / (baseline - market), per metric.

### DEV: 8740 of 8769 rows have closing odds

| model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|
| Closing market | 8740 | 0.195427 | 0.191240 | 0.966510 | 0.536613 |
| Baseline | 8740 | 0.208616 | 0.201240 | 1.013704 | 0.514645 |
| P1 | 8740 | 0.204753 | 0.198299 | 0.999035 | 0.521167 |

Gap closed by P1: RPS 29.29%, Brier 29.41%, LogLoss 31.08% (RPS: (0.208616 - 0.204753) / (0.208616 - 0.195427))

### VAL: 4291 of 4291 rows have closing odds

| model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|
| Closing market | 4291 | 0.185724 | 0.186530 | 0.943917 | 0.562340 |
| Baseline | 4291 | 0.200834 | 0.197826 | 1.003838 | 0.517828 |
| P1 | 4291 | 0.196652 | 0.194585 | 0.981172 | 0.525985 |

Gap closed by P1: RPS 27.68%, Brier 28.69%, LogLoss 37.83% (RPS: (0.200834 - 0.196652) / (0.200834 - 0.185724))

## 4. Rows with a rate outside [0.15, 6.0]

Definition A (primary): the Stage 2 baseline lambda_home or mu_away is outside the bounds. The same rows are used for both models. P1 clips its rates, so its recorded rates never fall outside; definition B therefore marks rows where P1's clip was active (a recorded P1 rate equals a bound).

### Definition A: baseline rate outside bounds

| split | rows | model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|---|---|
| DEV | outside | Baseline | 9 | 0.107516 | 0.071758 | 0.552575 | 0.888889 |
| DEV | outside | P1 | 9 | 0.099921 | 0.067661 | 0.432280 | 0.888889 |
| DEV | all other | Baseline | 8760 | 0.208234 | 0.200876 | 1.011967 | 0.515753 |
| DEV | all other | P1 | 8760 | 0.204440 | 0.197988 | 0.997666 | 0.522260 |
| VAL | outside | Baseline | 11 | 0.314522 | 0.359820 | 4.736614 | 0.454545 |
| VAL | outside | P1 | 11 | 0.234517 | 0.280062 | 1.555570 | 0.454545 |
| VAL | all other | Baseline | 4280 | 0.200542 | 0.197410 | 0.994245 | 0.517991 |
| VAL | all other | P1 | 4280 | 0.196555 | 0.194365 | 0.979695 | 0.526168 |

### Definition B: P1 clip active

| split | rows | model | n | RPS | Brier | LogLoss | Accuracy |
|---|---|---|---|---|---|---|---|
| DEV | outside | Baseline | 0 | n/a | n/a | n/a | n/a |
| DEV | outside | P1 | 0 | n/a | n/a | n/a | n/a |
| DEV | all other | Baseline | 8769 | 0.208130 | 0.200744 | 1.011496 | 0.516136 |
| DEV | all other | P1 | 8769 | 0.204332 | 0.197854 | 0.997085 | 0.522637 |
| VAL | outside | Baseline | 1 | 0.500000 | 0.666667 | 21.086411 | 0.000000 |
| VAL | outside | P1 | 1 | 0.485217 | 0.649028 | 4.444438 | 0.000000 |
| VAL | all other | Baseline | 4290 | 0.200764 | 0.197717 | 0.999157 | 0.517949 |
| VAL | all other | P1 | 4290 | 0.196585 | 0.194479 | 0.980364 | 0.526107 |

Rows in both A and B (DEV+VAL): 1.
Note on item 4: the 11 VAL rows where a baseline rate falls outside the bounds account for 0.00816 of P1's 0.02267
VAL log-loss gain (36%). On DEV, the 9 such rows account for 0.00012 of the 0.01441 gain (1%). On all other rows,
P1 still improves log-loss: DEV 1.011967 to 0.997666, VAL 0.994245 to 0.979695. The VAL log-loss "gap closed"
(37.8%) is inflated by these rows; the RPS figure (27.7%) is barely affected.

## Appendix: script used for items 2–4

Run from C:\dev\b12 as `python -X utf8 verify.py OUT.md`. It is not committed as a file, because it falls outside
the ownership list.

```python
"""Verification of the P1 headline (DEV/VAL only). Usage: python -X utf8 verify.py OUT.md (run from C:\\dev\\b12)."""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())
import exp_harness as harness  # noqa: E402
from exp_model import DEFAULT_PARAMS, make_params, run_filter  # noqa: E402
from run_experiments import FILTER_COLUMNS, ORDER, load_data, read_json, result_path  # noqa: E402


def main(out_path):
    df, train_df, test_index, home_adv = load_data()
    splits = harness.split_index(df, test_index)
    work = df.loc[~df.index.isin(test_index), FILTER_COLUMNS]
    harness.assert_no_test(work, test_index)
    p1 = read_json('candidate_p1')
    models = {'Baseline': run_filter(work, DEFAULT_PARAMS, home_adv),
              'P1': run_filter(work, make_params(**p1['params']), home_adv)}
    lines = []

    # 2. candidate_p1.json and the Holm table.
    with open(result_path('candidate_p1'), encoding='utf-8') as handle:
        lines += ['## 2. candidate_p1.json', '', '```json', handle.read().strip(), '```', '']
    results = [read_json(name) for name in ORDER]
    adjusted = harness.holm([r['p_one_sided'] for r in results])
    holm = pd.DataFrame([dict(experiment=r['experiment'], chosen=json.dumps(r['chosen']),
                              mean_delta_logloss=r['mean_delta_logloss'], ci_rows=r['ci_rows'],
                              ci99_low=r['ci99'][0], ci99_high=r['ci99'][1], p_one_sided=r['p_one_sided'],
                              p_holm=float(p), verdict=r['verdict']) for r, p in zip(results, adjusted)])
    lines += ['### Holm table (all six experiments)', '',
              'p_one_sided = (1 + #{bootstrap mean delta >= 0}) / 2001; Holm step-down over E1-E6. '
              'Acceptance used the locked rule, not these p-values.', '',
              harness.markdown_table(holm, 6), '']

    # 3. Market comparison on rows with closing odds.
    lines += ['## 3. Closing market vs baseline and P1 (rows with valid avg_ch/avg_cd/avg_ca)', '',
              'Market = normalised 1/odds of the closing market average; evaluation only (later information '
              'than T-60). Gap closed = (baseline - P1) / (baseline - market), per metric.', '']
    for split in ('dev', 'val'):
        rows = df.loc[splits[split]]
        market, mask = harness.market_probs(rows)
        on_market = rows.loc[mask]
        table = [dict(model='Closing market', **harness.summary(on_market, test_index, market[mask]))]
        for name, forecasts in models.items():
            table.append(dict(model=name, **harness.summary(on_market, test_index,
                                                            forecasts.loc[on_market.index, harness.PROB_COLUMNS])))
        table = pd.DataFrame(table).set_index('model')
        gaps = {metric: (table.loc['Baseline', metric] - table.loc['P1', metric])
                / (table.loc['Baseline', metric] - table.loc['Closing market', metric])
                for metric in ('RPS', 'Brier', 'LogLoss')}
        lines += [f'### {split.upper()}: {mask.sum()} of {len(rows)} rows have closing odds', '',
                  harness.markdown_table(table.reset_index(), 6), '',
                  'Gap closed by P1: ' + ', '.join(f'{metric} {value:.2%}' for metric, value in gaps.items())
                  + f" (RPS: ({table.loc['Baseline', 'RPS']:.6f} - {table.loc['P1', 'RPS']:.6f}) / "
                  f"({table.loc['Baseline', 'RPS']:.6f} - {table.loc['Closing market', 'RPS']:.6f}))", '']

    # 4. Rows with extreme rates.
    low, high = DEFAULT_PARAMS['rate_bounds']
    base = models['Baseline']
    outside_base = (base.lambda_home < low) | (base.lambda_home > high) | (base.mu_away < low) | (base.mu_away > high)
    clipped = models['P1']
    clip_active = clipped.lambda_home.isin([low, high]) | clipped.mu_away.isin([low, high])
    lines += [f'## 4. Rows with a rate outside [{low}, {high}]', '',
              'Definition A (primary): the Stage 2 baseline lambda_home or mu_away is outside the bounds. '
              'The same rows are used for both models. P1 clips its rates, so its recorded rates never fall '
              'outside; definition B therefore marks rows where P1\'s clip was active '
              '(a recorded P1 rate equals a bound).', '']
    for label, flag in (('A: baseline rate outside bounds', outside_base), ('B: P1 clip active', clip_active)):
        table = []
        for split in ('dev', 'val'):
            rows = df.loc[splits[split]]
            for subset, ids in (('outside', rows.index[flag.loc[rows.index].to_numpy()]),
                                ('all other', rows.index[~flag.loc[rows.index].to_numpy()])):
                for name, forecasts in models.items():
                    if len(ids):
                        table.append(dict(split=split.upper(), rows=subset, model=name,
                                          **harness.summary(df.loc[ids], test_index,
                                                            forecasts.loc[ids, harness.PROB_COLUMNS])))
                    else:
                        table.append(dict(split=split.upper(), rows=subset, model=name, n=0))
        lines += [f'### Definition {label}', '', harness.markdown_table(pd.DataFrame(table), 6), '']
    overlap = (outside_base & clip_active).loc[splits['dev'].union(splits['val'])].sum()
    lines += [f'Rows in both A and B (DEV+VAL): {int(overlap)}.', '']

    with open(out_path, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines))
    print('\n'.join(lines))


if __name__ == '__main__':
    main(sys.argv[1])
```
