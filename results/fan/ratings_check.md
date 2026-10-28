# Team ratings: checks

Parameters were fixed before 2026-27 data was fetched. Forecasts were recomputed after the matches were played and are not timestamped before kickoff.

DESCRIPTIVE: ratings from the final states of the frozen P2 goals-only filter run over H and the 2026-27 snapshot 2026-10-26; no test, no claim.

Model: `results/p2/candidate_p2.json` (sha256 bf7d5226316fe2cb4473e7120c624802f7dcdbd651b603200747f179728b0e3f); code commit cc60ae5a86244ec73a916c957cf87e4d479cbcef (fan_features.py sha256 090de447abb7125a..., differs from that commit: True).

Every bar: model uncertainty, not measured accuracy.

Factors: exp(posterior mean - centre), centre = mean of the posterior means over the league's active 2026-27 teams. The model has no intercept, so uncentred values are not interpretable. An attack factor above one scores more than the league average side; a defence factor below one concedes less (lower is better). Overall = attack factor / defence factor. Bars are exp(centred mean plus or minus one sd) from the filter's own variance: a diagonal Gaussian (Laplace-style) approximation, centring uncertainty ignored, coverage not checked. Per-team factors, sds and ranks are in `ratings.json`.

## Excluded teams (flagged aliases; names not merged)

- TUR Super Lig: Erzurumspor, alias of Erzurum BB (see `results/live2627/data_audit.md`)

## 1. Factors average to one on the log scale within each league

Result: PASS in all eight leagues (largest absolute sum of log factors, attack and defence, is below `CENTRING_TOLERANCE` in `fan_features.py`; the per-league values are in `ratings.json`).

## 2. Top three per league by overall rank

- NLD Eredivisie: Feyenoord, PSV Eindhoven, Ajax
- PRT Liga 1: Benfica, Porto, Sp Lisbon
- TUR Super Lig: Fenerbahce, Galatasaray, Trabzonspor
- ESP La Liga: Barcelona, Real Madrid, Ath Madrid
- FRA Ligue 1: Paris SG, Lens, Lille
- ENG Premier League: Arsenal, Man City, Brighton
- ITA Serie A: Inter, Roma, Como
- DEU Bundesliga 1: Bayern Munich, Dortmund, Leverkusen

The names are listed for reading by eye; this file does not judge them.

## 3. Newcomer sd against the league median of established teams

10 of 10 newcomers have both the attack sd and the defence sd above their league's median for established teams (per-team values are in `ratings.json`).

## 4. sd against matches played (established teams only)

The expectation that defence sd falls as matches played rises did not hold: defence sd rises with matches played (Spearman +0.456) while attack sd falls (Spearman -0.396); n = 139 established teams.

- attack: Spearman -0.396 (n = 139)
- defence: Spearman +0.456 (n = 139)
- Smallest |rho| that is significant at the usual two-sided level with n = 139 established teams: about 0.17 (normal approximation, n minus one in the denominator). This is a significance threshold for established teams only, not a power calculation.
- Defence sd range across the established teams: 0.177 to 0.240 (n = 139), so the half-width factor of a defence bar ranges from 1.19 to 1.27 times.

Defence bars do not narrow with more matches. This most likely reflects how the model's variance behaves. A simulation reproduced the signs but could not separate this from team selection, so treat it as unconfirmed (see ratings_check.md).

## 5. What the model implies (simulation)

Synthetic leagues with no real data, generated from the model's own prior and random walk with the fitted parameters, then filtered by the same frozen code. This shows what the model implies, not a football finding. The design constants and the seed are in `ratings_sim.json`.

- seed 20261028
- defence: Spearman +0.236 (n = 136 synthetic established teams)
- attack: Spearman -0.130 (n = 136 synthetic established teams)

In the simulation the signs match the real teams: defence sd rises and attack sd falls with matches played. Under this design the filter's variance dynamics and the exit of the weakest teams each season both act, and the simulation does not separate the two.

