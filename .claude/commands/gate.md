Run the verification gate: `python -X utf8 tools/gate.py $ARGUMENTS` (add `--fast` to skip the anchor run).
Print only the final block: one line per check and the GATE verdict. No other output, no commentary.
If the verdict is FAIL, run /diagnose on the failing lines only (read-only). Never change a spec, an anchor,
tools/ownership.txt or results/claims.json to make the gate pass; report the failure and wait for the user.
