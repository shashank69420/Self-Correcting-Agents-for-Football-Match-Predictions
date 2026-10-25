"""Mechanical verification gate. Run from anywhere: python -X utf8 tools/gate.py [--fast]

Prints one line per check, then "GATE: PASS" or "GATE: FAIL (n)"; exit code 0 or 1. --fast skips the anchor run.
The constants below are the expected values. Changing them needs the user's approval.
"""
import fnmatch
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import verify_claims  # noqa: E402

EXPECTED_BRANCH = 'main'
ANCHORS = dict(stage1_rps='0.2057', stage2_rps='0.2060', all_3829_rps='0.2059', change_scale='0')
FORBIDDEN_PREFIXES = ('data/', 'outputs/', 'venv/')
FORBIDDEN_SUFFIXES = ('.csv', '.pkl')
TEST_ONCE_PHRASE = 'one-shot test scoring'


def run(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace',
                          **kwargs)


def git(*args):
    return run(['git', *args])


def check_branch_and_status():
    branch = git('branch', '--show-current').stdout.strip()
    status = git('status', '--porcelain').stdout.splitlines()
    dirty = [line for line in status if line.startswith('??') or line[1:2] != ' ']
    staged = [line for line in status if line[0:1] not in (' ', '?')]
    results = [(branch == EXPECTED_BRANCH, f'branch: {branch}' if branch == EXPECTED_BRANCH
                else f'branch: actual {branch!r}, expected {EXPECTED_BRANCH!r}')]
    detail = f'{len(staged)} staged file(s) allowed' if not dirty else f'unstaged or untracked: {dirty[:6]}'
    results.append((not dirty, f'status: clean ({detail})' if not dirty else f'status: not clean; {detail}, expected none'))
    return results


def check_anchors():
    result = run([sys.executable, '-X', 'utf8', 'main.py'])
    text = result.stdout
    found = dict(
        stage1_rps=re.search(r'^Stage 1:\s+([0-9.]+)\s+[0-9.]+\s+[0-9.]+\s*$', text, re.M),
        stage2_rps=re.search(r'^Stage 2:\s+([0-9.]+)\s+[0-9.]+\s+[0-9.]+\s*$', text, re.M),
        all_3829_rps=re.search(r'Stage 2 RPS on ALL 3829 held-out matches: ([0-9.]+)', text),
        change_scale=re.search(r'Selected CHANGE_SCALE: (\S+)', text))
    actual = {key: (match.group(1) if match else None) for key, match in found.items()}
    ok = result.returncode == 0 and actual == ANCHORS
    return [(ok, 'anchors: ' + ', '.join(f'{k} {v}' for k, v in actual.items()) if ok
             else f'anchors: actual {actual} (exit {result.returncode}), expected {ANCHORS}')]


def check_tests():
    result = run([sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'tests'])
    output = result.stdout + result.stderr
    ran = re.search(r'Ran (\d+) tests?', output)
    if result.returncode == 0:
        return [(True, f'tests: {ran.group(1) if ran else "?"} ran, OK')]
    skipped, total, failed = [], 0, []
    for name in sorted(os.listdir(os.path.join(ROOT, 'tests'))):
        if not (name.startswith('test_') and name.endswith('.py')):
            continue
        part = run([sys.executable, '-X', 'utf8', '-m', 'unittest', f'tests.{name[:-3]}'])
        text = part.stdout + part.stderr
        count = re.search(r'Ran (\d+) tests?', text)
        if part.returncode != 0 and "No module named 'pytest'" in text:
            skipped.append(f'tests/{name}')
        elif part.returncode != 0:
            failed.append(f'tests/{name}')
        else:
            total += int(count.group(1)) if count else 0
    if failed:
        return [(False, f'tests: failing {failed}, expected none; see: python -m unittest discover -s tests')]
    return [(True, f'tests: {total} ran, OK; SKIPPED (pytest not installed): {skipped}')]


def check_claims():
    failures = verify_claims.verify(ROOT)
    if failures:
        return [(False, f'claims: {len(failures)} failing, expected 0; first: {failures[0]}')]
    return [(True, 'claims: every number in results/FINDINGS.md is backed')]


def check_hygiene():
    tracked = git('ls-files').stdout.splitlines()
    bad = [path for path in tracked if path.startswith(FORBIDDEN_PREFIXES) or path.endswith(FORBIDDEN_SUFFIXES)]
    return [(not bad, 'hygiene: no data/, outputs/, venv/, *.csv or *.pkl tracked' if not bad
             else f'hygiene: tracked forbidden files {bad[:6]}, expected none')]


def load_ownership():
    patterns = []
    with open(os.path.join(ROOT, 'tools', 'ownership.txt'), encoding='utf-8') as handle:
        for line in handle:
            line = line.split('#')[0].strip()
            if line:
                parts = line.split()
                patterns.append((parts[0], 'append-only' in parts[1:]))
    return patterns


def check_ownership():
    base = git('merge-base', 'HEAD', 'main').stdout.strip()
    if not base:
        return [(False, 'ownership: no merge-base with main, expected one')]
    changed = [p for p in git('diff', '--name-only', base).stdout.splitlines() if p]
    patterns = load_ownership()
    outside, removed = [], []
    for path in changed:
        rule = next(((p, a) for p, a in patterns if fnmatch.fnmatch(path, p)), None)
        if rule is None:
            outside.append(path)
        elif rule[1]:
            diff = git('diff', '-U0', base, '--', path).stdout.splitlines()
            if any(line.startswith('-') and not line.startswith('---') for line in diff):
                removed.append(path)
    ok = not outside and not removed
    return [(ok, f'ownership: {len(changed)} changed file(s), all allowed' if ok
             else f'ownership: outside the allowlist {outside}; lines removed from append-only files {removed}; '
                  'expected none')]


def check_test_once():
    with open(os.path.join(ROOT, 'DECISIONS.md'), encoding='utf-8') as handle:
        entries = handle.read().lower().count(TEST_ONCE_PHRASE)
    subjects = [s for s in git('log', '--format=%s').stdout.splitlines() if TEST_ONCE_PHRASE in s.lower()]
    ok = entries == 1 and len(subjects) == 1
    return [(ok, 'test-once: 1 DECISIONS entry, 1 commit' if ok
             else f'test-once: actual {entries} DECISIONS entries and {len(subjects)} commits, expected 1 and 1')]


def main():
    fast = '--fast' in sys.argv[1:]
    checks = [check_branch_and_status]
    if not fast:
        checks.append(check_anchors)
    checks += [check_tests, check_claims, check_hygiene, check_ownership, check_test_once]
    lines, failures = [], 0
    for check in checks:
        for ok, message in check():
            lines.append(f'[{"PASS" if ok else "FAIL"}] {message}')
            failures += 0 if ok else 1
    if failures:
        verdict = f'GATE: FAIL ({failures})'
    else:
        verdict = 'GATE: PASS (fast, anchors not run)' if fast else 'GATE: PASS'
    print('\n'.join(lines + [verdict]))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
