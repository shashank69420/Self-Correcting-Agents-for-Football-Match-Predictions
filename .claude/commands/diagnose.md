Diagnose the most recent unexpected result. Context from the user: $ARGUMENTS
Edit no source file. Run read-only commands. Write only to outputs/diagnose/.
1. State the expectation and the observed value, one line each.
2. Implementation check: recompute the headline statistic on a random
   2,000-row subsample with a separate minimal implementation that shares no
   helper code. Compare with the main result. Check sign conventions against
   the spec text.
3. Data check: row counts after each filter, coverage by season, missing
   share, and any row dated on or after the estimation cutoff.
4. Noise check: permutation placebo of the key features across matches within
   season, 200 permutations, seed 20261019. Report the share that pass the
   gate (expect about 5% or less).
5. Power check: the smallest effect the current standard errors could detect,
   compared with the plausible effect.
6. Translate the effect into expected goals and expected LogLoss change.
7. Report in under 20 lines: classification, evidence, options tagged
   [pre-registered] or [post-hoc], one recommendation, what needs my approval.
