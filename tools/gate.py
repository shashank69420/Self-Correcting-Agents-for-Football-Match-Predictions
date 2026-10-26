"""Mechanical verification gate. Run from anywhere: python -X utf8 tools/gate.py [--fast]

Prints one line per check, then "GATE: PASS" or "GATE: FAIL (n)"; exit code 0 or 1. --fast skips the anchor run.
The constants below are the expected values. Changing them needs the user's approval.
"""
import fnmatch
import importlib.util
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import verify_claims  # noqa: E402

EXPECTED_BRANCH = 'main'
EXPECTED_TESTS = 64
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
    """Full suite under tests/ with pytest when it is importable, else unittest; total must equal EXPECTED_TESTS."""
    if importlib.util.find_spec('pytest') is not None:
        runner = 'pytest'
        result = run([sys.executable, '-X', 'utf8', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', 'tests'])
        counts = re.findall(r'(\d+) (passed|failed|skipped|errors?|xfailed|xpassed)', result.stdout)
        total = sum(int(n) for n, _ in counts)
    else:
        runner = 'unittest'
        result = run([sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'tests'])
        ran = re.search(r'Ran (\d+) tests?', result.stdout + result.stderr)
        total = int(ran.group(1)) if ran else 0
    ok = result.returncode == 0 and total == EXPECTED_TESTS
    return [(ok, f'tests: {total} ran with {runner}, OK' if ok
             else f'tests: actual {total} with {runner} (exit {result.returncode}), expected {EXPECTED_TESTS} passing')]


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


def ownership_base():
    with open(os.path.join(ROOT, 'tools', 'ownership.txt'), encoding='utf-8') as handle:
        for line in handle:
            match = re.match(r'#\s*base:\s*([0-9a-f]{7,40})', line)
            if match:
                return match.group(1)
    return ''


def ownership_failures(changed, patterns, removes_lines):
    """Paths outside the allowlist, and append-only paths for which removes_lines(path) is true."""
    outside, removed = [], []
    for path in changed:
        rule = next(((p, a) for p, a in patterns if fnmatch.fnmatch(path, p)), None)
        if rule is None:
            outside.append(path)
        elif rule[1] and removes_lines(path):
            removed.append(path)
    return outside, removed


def check_ownership():
    base = ownership_base()
    if not git('cat-file', '-e', f'{base}^{{commit}}').returncode == 0:
        return [(False, f'ownership: base commit {base!r} not found')]
    # Committed plus staged changes: the same list as <base> HEAD on a clean tree, and it also sees staged files.
    changed = [p for p in git('diff', '--cached', '--name-only', base).stdout.splitlines() if p]

    def removes_lines(path):
        diff = git('diff', '--cached', '-U0', base, '--', path).stdout.splitlines()
        return any(line.startswith('-') and not line.startswith('---') for line in diff)

    outside, removed = ownership_failures(changed, load_ownership(), removes_lines)
    ok = not outside and not removed
    return [(ok, f'ownership: {len(changed)} changed file(s) since {base[:7]}, all allowed' if ok
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
