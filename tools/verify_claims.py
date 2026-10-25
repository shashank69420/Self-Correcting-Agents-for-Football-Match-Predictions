"""Checks that every number in results/FINDINGS.md is backed by a repository file.

python -X utf8 tools/verify_claims.py

results/claims.json holds one entry per number:
  {"id", "value", "source", "locator"}            value as written in FINDINGS.md; locator is a regex that must
                                                  match in the source file, and the match must contain the value
                                                  (or "source_value" when the source writes it differently)
  {"id", "value", "derived": {"inputs": [id, id], "formula": "a - b"}}   recomputed from the two input claims
It fails when a value is not in FINDINGS.md, a source is missing or untracked, a locator does not match, a derived
value does not recompute, or FINDINGS.md contains a number that no claim covers.

Coverage is by value: a number is covered when some claim has that exact value. It does not tie each occurrence of
a repeated value to its own claim.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINDINGS = 'results/FINDINGS.md'
CLAIMS = 'results/claims.json'

# Text removed before looking for numbers: section numbers, dates, season labels, stage ranges and labels,
# the T-60 lead time and the sha256 name. Changing this list changes what counts as a number.
IGNORE = [r'^#+ \d+\.', r'\b20\d\d-\d\d-\d\d\b', r'\b20\d\d-\d\d(?:\d\d)?\b', r'\b\d{1,2} [A-Z][a-z]+ 20\d\d\b',
          r'\bStages? \d+-\d+\b', r'\bStages? \d+(?: (?:to|and) \d+)?', r'\bT-60\b', r'\bsha256\b']
NUMBER = r'(?<![\w.])[-+]?\d+(?:,\d{3})*(?:\.\d+)?%?(?![\w])'
FORMULA = re.compile(r'^[ab0-9+\-*/(). ]+$')


def read(root, path):
    with open(os.path.join(root, path), encoding='utf-8') as handle:
        return handle.read()


def numbers_in(text):
    for pattern in IGNORE:
        text = re.sub(pattern, ' ', text, flags=re.M)
    return set(re.findall(NUMBER, text))


def tracked(root, path):
    result = subprocess.run(['git', 'ls-files', '--', path], cwd=root, capture_output=True, text=True)
    return result.returncode == 0 and path in result.stdout.split('\n')


def verify(root=ROOT, findings=FINDINGS, claims_path=CLAIMS, check_tracked=True):
    """Returns a list of failure strings (empty when every claim holds)."""
    failures = []
    try:
        text = read(root, findings)
        claims = json.loads(read(root, claims_path))['claims']
    except (OSError, ValueError, KeyError) as error:
        return [f'cannot load {findings} or {claims_path}: {error}']
    ids = {}
    for claim in claims:
        if claim.get('id') in ids:
            failures.append(f"{claim.get('id')}: duplicate id")
        ids[claim.get('id')] = claim
    for claim in claims:
        name, value = claim.get('id'), str(claim.get('value'))
        if value not in text:
            failures.append(f'{name}: value {value!r} not in {findings}')
            continue
        if 'derived' in claim:
            failures += derived_failures(name, value, claim['derived'], ids)
            continue
        source = claim.get('source', '')
        if not source or not os.path.isfile(os.path.join(root, source)):
            failures.append(f'{name}: source file missing: {source!r}')
            continue
        if check_tracked and not tracked(root, source):
            failures.append(f'{name}: source is not tracked by git: {source}')
            continue
        match = re.search(claim.get('locator', ''), read(root, source), flags=re.M)
        if not match:
            failures.append(f'{name}: locator does not match in {source}: {claim.get("locator")!r}')
        elif str(claim.get('source_value', value)) not in match.group(0):
            failures.append(f'{name}: {claim.get("source_value", value)!r} not inside the locator match '
                            f'{match.group(0)!r} in {source}')
    covered = {str(claim.get('value')) for claim in claims}
    for number in sorted(numbers_in(text) - covered):
        failures.append(f'uncovered number in {findings}: {number}')
    return failures


def derived_failures(name, value, derived, ids):
    inputs = derived.get('inputs', [])
    formula = derived.get('formula', '')
    if len(inputs) != 2 or any(i not in ids or 'derived' in ids[i] for i in inputs):
        return [f'{name}: derived claim needs two non-derived input claims, got {inputs}']
    if not FORMULA.match(formula):
        return [f'{name}: formula not allowed: {formula!r}']
    a, b = (float(str(ids[i].get('source_value', ids[i]['value'])).replace(',', '').rstrip('%')) for i in inputs)
    result = eval(formula, {'__builtins__': {}}, {'a': a, 'b': b})  # restricted to a, b, digits and + - * /
    decimals = len(value.split('.')[1]) if '.' in value else 0
    if f'{result:.{decimals}f}' != value:
        return [f'{name}: {formula} with a={a}, b={b} gives {result:.{decimals}f}, expected {value}']
    return []


def main():
    failures = verify()
    for failure in failures:
        print('FAIL', failure)
    with open(os.path.join(ROOT, CLAIMS), encoding='utf-8') as handle:
        count = len(json.load(handle)['claims'])
    print(f'claims: {count} checked, {len(failures)} failing')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
