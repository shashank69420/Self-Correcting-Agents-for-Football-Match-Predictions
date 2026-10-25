Reproduces the one-shot TEST result. Deterministic. Rerunning is a reproduction, not a new test. Do not change parameters.

Files: `test_once.py` (`primary`, then `secondary`) and `split_test.py` (descriptive outside/other split), copied
unmodified (sha256 identical) from the session scratchpad. Run from the repository root, in this order:

    python -X utf8 results/experiments/test_once.py primary
    python -X utf8 results/experiments/test_once.py secondary
    python -X utf8 results/experiments/split_test.py

Caution: the scripts write to `results/experiments/test_once.md` (`primary` overwrites it, the others append). The
committed `test_once.md` is the record; after a reproduction, restore it with `git show HEAD:results/experiments/test_once.md`.
The output of the reproduction run is in `test_once_repro.txt`.
