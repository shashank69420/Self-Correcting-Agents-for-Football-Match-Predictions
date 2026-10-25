"""Descriptive outside/other split of already-scored TEST rows. Run from C:\dev\b12."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exp_harness as harness
from metrics import outcome_classes
from test_once import forecasts, OUT

df, train_df, test_index, params, p1, verdicts, confirmed, baseline, candidate, equal = forecasts()
test = df.loc[test_index]
actual = outcome_classes(test)
cols = harness.PROB_COLUMNS
base = harness.row_scores(baseline.loc[test_index, cols].to_numpy(float), actual)['LogLoss']
cand = harness.row_scores(candidate.loc[test_index, cols].to_numpy(float), actual)['LogLoss']
b = baseline.loc[test_index]
outside = ((b.lambda_home < 0.15) | (b.lambda_home > 6.0) | (b.mu_away < 0.15) | (b.mu_away > 6.0)).to_numpy()
known = set(train_df.team_home) | set(train_df.team_away)
common = (test.team_home.isin(known) & test.team_away.isin(known)).to_numpy()
lines = ['', '## DESCRIPTIVE SPLIT, post-scoring, not a test', '',
         'TEST, one-shot, retrospective. A split of the already-scored rows above; no new comparison, no CI, no decision. '
         'Outside = baseline lambda_home or mu_away outside [0.15, 6.0] (same rows for both models); other = the rest.', '']
for name, rows in (('All 3829 TEST rows', np.ones(len(test), bool)), ('3545 common rows', common)):
    records = []
    for label, m in (('outside', rows & outside), ('other', rows & ~outside), ('total', rows)):
        records.append({'group': label, 'n': int(m.sum()),
                        'baseline log-loss': base[m].mean() if m.any() else np.nan,
                        'P1 log-loss': cand[m].mean() if m.any() else np.nan,
                        'summed gain (baseline - P1)': (base[m] - cand[m]).sum()})
    t = pd.DataFrame(records)
    total = t.loc[t.group == 'total', 'summed gain (baseline - P1)'].item()
    out_gain = t.loc[t.group == 'outside', 'summed gain (baseline - P1)'].item()
    lines += [f'### {name}', '', harness.markdown_table(t, 6), '',
              f'Share of the total log-loss gain from outside rows: {out_gain / total:.2%} '
              f'({int((rows & outside).sum())} of {int(rows.sum())} rows).', '']
text = '\n'.join(lines)
open(OUT, 'a', encoding='utf-8').write(text + '\n')
print(text)
