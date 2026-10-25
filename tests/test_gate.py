"""Synthetic tests for tools/verify_claims.py and the gate's ownership check. Run: python -X utf8 -m unittest tests.test_gate -v"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import gate  # noqa: E402
import verify_claims  # noqa: E402

FINDINGS_TEXT = '## 1. Data\nThe model scored 0.2057 on 3,545 rows (derived gap 0.0131).\n'
SOURCE_TEXT = 'Stage 1 RPS 0.2057\nrows: 3545\nStage 2 RPS 0.2188\nmarket 0.2057\n'


def claim(**fields):
    return dict(source='src.txt', **fields)


class VerifyClaimsTest(unittest.TestCase):
    def verify(self, claims, findings=FINDINGS_TEXT, source=SOURCE_TEXT):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, 'results'))
            with open(os.path.join(root, 'results', 'FINDINGS.md'), 'w', encoding='utf-8') as handle:
                handle.write(findings)
            with open(os.path.join(root, 'results', 'claims.json'), 'w', encoding='utf-8') as handle:
                json.dump(dict(claims=claims), handle)
            if source is not None:
                with open(os.path.join(root, 'src.txt'), 'w', encoding='utf-8') as handle:
                    handle.write(source)
            return verify_claims.verify(root, check_tracked=False)

    def good(self):
        return [claim(id='a', value='0.2057', locator=r'Stage 1 RPS 0\.2057'),
                claim(id='b', value='3,545', locator=r'rows: 3545', source_value='3545'),
                claim(id='c', value='0.2188', locator=r'Stage 2 RPS 0\.2188'),
                dict(id='d', value='0.0131', derived=dict(inputs=['c', 'a'], formula='a - b'))]

    def findings_with_all(self):
        return FINDINGS_TEXT.replace('0.0131).', '0.0131; Stage 2 0.2188).')

    def test_good_claims_pass(self):
        self.assertEqual(self.verify(self.good(), findings=self.findings_with_all()), [])

    def test_wrong_value_fails(self):
        claims = self.good()
        claims[0]['value'] = '0.2058'  # not in FINDINGS and not what the source says
        failures = self.verify(claims, findings=self.findings_with_all())
        self.assertTrue(any('0.2058' in f for f in failures))
        claims = self.good()
        claims[0]['locator'] = r'Stage 1 RPS 0\.2099'  # FINDINGS has the value, the source does not
        failures = self.verify(claims, findings=self.findings_with_all())
        self.assertTrue(any('locator does not match' in f for f in failures))
        claims = self.good()
        claims[0]['locator'] = r'Stage 2 RPS'  # the match does not contain the value
        failures = self.verify(claims, findings=self.findings_with_all())
        self.assertTrue(any('not inside the locator match' in f for f in failures))

    def test_missing_source_fails(self):
        failures = self.verify(self.good(), findings=self.findings_with_all(), source=None)
        self.assertTrue(any('source file missing' in f for f in failures))
        claims = self.good()
        claims[1]['source'] = 'no_such_file.txt'
        self.assertTrue(any('no_such_file.txt' in f for f in
                            self.verify(claims, findings=self.findings_with_all())))

    def test_uncovered_number_fails(self):
        failures = self.verify(self.good(), findings=self.findings_with_all() + 'A new figure: 0.4321.\n')
        self.assertIn('uncovered number in results/FINDINGS.md: 0.4321', failures)

    def test_ignored_text_is_not_a_number(self):
        extra = '## 2. Heading\nDates 2026-10-19 and 2019-20, Stage 3, Stages 1-5, 1X2, a1b2 and T-60.\n'
        self.assertEqual(self.verify(self.good(), findings=self.findings_with_all() + extra), [])

    def test_derived_claim_is_recomputed(self):
        claims = self.good()
        claims[3]['value'] = '0.0132'
        findings = self.findings_with_all().replace('0.0131', '0.0132')
        failures = self.verify(claims, findings=findings)
        self.assertTrue(any('gives 0.0131, expected 0.0132' in f for f in failures))
        claims = self.good()
        claims[3]['derived']['formula'] = '__import__("os")'
        self.assertTrue(any('formula not allowed' in f for f in
                            self.verify(claims, findings=self.findings_with_all())))

    def test_duplicate_id_fails(self):
        claims = self.good() + [claim(id='a', value='0.2057', locator=r'market 0\.2057')]
        self.assertTrue(any('duplicate id' in f for f in self.verify(claims, findings=self.findings_with_all())))

    def test_repository_claims_hold(self):
        self.assertEqual(verify_claims.verify(), [])


class OwnershipTest(unittest.TestCase):
    def test_changed_files_against_allowlist(self):
        patterns = gate.load_ownership()
        no_removals = lambda path: False  # noqa: E731
        allowed = ['exp_model.py', 'results/experiments/E1.md', 'tools/gate.py', 'DECISIONS.md']
        self.assertEqual(gate.ownership_failures(allowed, patterns, no_removals), ([], []))
        outside, _ = gate.ownership_failures(allowed + ['main.py'], patterns, no_removals)
        self.assertEqual(outside, ['main.py'])
        _, removed = gate.ownership_failures(allowed, patterns, lambda path: path == 'DECISIONS.md')
        self.assertEqual(removed, ['DECISIONS.md'])


if __name__ == '__main__':
    unittest.main()
