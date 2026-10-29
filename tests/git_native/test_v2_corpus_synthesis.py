"""Strict corpus receipt, reviewer verdict and independently reproduced refusal tests."""
import copy
import hashlib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from pcbknowledge.v2.synthesis import digest, evaluate_corpus
from tests.git_native.test_v2_synthesis import graph


class CorpusSynthesisTests(unittest.TestCase):
    def setUp(self):
        self.bundle = SimpleNamespace(commit='a' * 40, catalog=Mock(), briefs={'G1': {'id': 'G1'}})
        self.options = {'orchestrator': 'agent:orchestrator', 'skill_text': 'Exact skill', 'bundle_sha256': 'b' * 64}

    def attempts(self, negative=False):
        result = []
        for index in range(3):
            key = 'refusal' if negative else 'graph'
            output = ({'brief': 'G1', 'code': 'CHECK_FAILED', 'path': 'functions.usb_sink',
                       'reason': 'Required voltage is unsupported.'} if negative else graph('fresh-' + str(index)))
            transcript = [{'query': {'kind': 'Q6'}, 'response': {'records': []}}]
            receipt = {'agent': 'agent:author-' + str(index), 'reviewer': 'agent:reviewer',
                       'orchestrator': self.options['orchestrator'], 'mode': 'QUERY_MEDIATED',
                       'bundle_commit': self.bundle.commit, 'bundle_sha256': self.options['bundle_sha256'],
                       'brief_sha256': digest({'id': 'G1'}), key + '_sha256': digest(output),
                       'reference_accessed': False, 'transcript_sha256': digest(transcript),
                       'skill_sha256': hashlib.sha256(self.options['skill_text'].encode()).hexdigest(),
                       'reviewer_verdict': 'EQUIVALENT', 'equivalence_review': 'Reviewed complete preserved output.'}
            result.append({key: output, 'transcript': transcript, 'receipt': receipt})
        return result

    def evaluate(self, attempts, **kwargs):
        return evaluate_corpus(self.bundle, 'G1', attempts, **self.options, **kwargs)

    @patch('pcbknowledge.v2.synthesis.validate_expansion')
    @patch('pcbknowledge.v2.synthesis.expand', return_value={'status': 'EXPANDED', 'checks': [], 'refusals': []})
    def test_receipt_independence_hashes_and_controlled_verdict(self, *_):
        attempts = self.attempts()
        self.assertEqual(self.evaluate(attempts, reference=graph())['passed'], 3)
        changes = {'agent': 'agent:author-1', 'reviewer': 'agent:author-1', 'orchestrator': 'agent:other',
                   'bundle_commit': 'wrong', 'bundle_sha256': 'c' * 64, 'brief_sha256': 'c' * 64,
                   'skill_sha256': 'c' * 64, 'transcript_sha256': 'c' * 64, 'graph_sha256': 'c' * 64,
                   'reference_accessed': True, 'equivalence_review': '', 'mode': 'SANDBOXED',
                   'reviewer_verdict': 'APPROVED'}
        for key, value in changes.items():
            bad = copy.deepcopy(attempts)
            bad[0]['receipt'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.evaluate(bad, reference=graph())
        del attempts[0]['receipt']['reviewer_verdict']
        with self.assertRaisesRegex(ValueError, 'reviewer verdict'):
            self.evaluate(attempts, reference=graph())
        for count in (2, 4):
            with self.assertRaises(ValueError):
                self.evaluate((self.attempts() * 2)[:count], reference=graph())

    @patch('pcbknowledge.v2.synthesis.validate_expansion')
    @patch('pcbknowledge.v2.synthesis.expand', return_value={'status': 'EXPANDED', 'checks': [], 'refusals': []})
    def test_negative_verdict_cannot_be_overridden_by_prose_or_topology(self, *_):
        for mismatched in (False, True):
            attempts = self.attempts()
            for attempt in attempts:
                if mismatched:
                    attempt['graph']['connections'][0]['endpoints'][0]['port'] = 'WRONG'
                attempt['receipt']['graph_sha256'] = digest(attempt['graph'])
                attempt['receipt']['reviewer_verdict'] = 'NOT_EQUIVALENT'
                attempt['receipt']['equivalence_review'] = 'NOT EQUIVALENT; reject.'
            result = self.evaluate(attempts, reference=graph())
            self.assertEqual((result['status'], result['passed']), ('FAIL', 0))
            self.assertTrue(all(not row['reference_equivalent'] for row in result['attempts']))

    def test_cross_brief_and_transcript_tampering_fail_before_expansion(self):
        attempts = self.attempts()
        attempts[0]['graph']['brief'] = 'G2'
        attempts[0]['receipt']['graph_sha256'] = digest(attempts[0]['graph'])
        with patch('pcbknowledge.v2.synthesis.expand') as expand:
            with self.assertRaisesRegex(ValueError, 'brief differs'):
                self.evaluate(attempts, reference=graph())
            reference = graph()
            reference['brief'] = 'G2'
            with self.assertRaises(ValueError):
                self.evaluate(self.attempts(), reference=reference)
            attempts = self.attempts()
            attempts[0]['transcript'][0]['response'] = {'tampered': True}
            with self.assertRaises(ValueError):
                self.evaluate(attempts, reference=graph())
            expand.assert_not_called()

    @patch('pcbknowledge.v2.synthesis.validate_expansion')
    def test_positive_two_of_three_threshold(self, _):
        yes = {'status': 'EXPANDED', 'checks': [], 'refusals': []}
        no = {'status': 'REFUSED', 'checks': [], 'refusals': ['synthetic']}
        for outputs, status, passed in (([yes, yes, yes, no], 'PASS', 2), ([yes, yes, no, no], 'FAIL', 1)):
            with patch('pcbknowledge.v2.synthesis.expand', side_effect=outputs):
                result = self.evaluate(self.attempts(), reference=graph())
                self.assertEqual((result['status'], result['passed']), (status, passed))

    @patch('pcbknowledge.v2.requirements.assess_brief')
    def test_negative_three_identical_refusals_require_independent_replay_and_exact_identity(self, assess):
        expected = {'code': 'CHECK_FAILED', 'path': 'functions.usb_sink'}
        assess.return_value = [expected]
        attempts = self.attempts(True)
        self.assertEqual(self.evaluate(attempts, expected_refusal=expected)['passed'], 3)
        assess.return_value = []
        self.assertEqual(self.evaluate(attempts, expected_refusal=expected)['status'], 'FAIL')
        assess.return_value = [expected]
        for key, value in (('brief', 'G2'), ('code', 'OTHER'), ('path', 'other'), ('reason', '')):
            bad = copy.deepcopy(attempts)
            bad[0]['refusal'][key] = value
            bad[0]['receipt']['refusal_sha256'] = digest(bad[0]['refusal'])
            result = self.evaluate(bad, expected_refusal=expected)
            self.assertEqual((result['status'], result['passed']), ('FAIL', 2))
        attempts[0]['graph'] = graph('invented')
        with self.assertRaises(ValueError):
            self.evaluate(attempts, expected_refusal=expected)

    @patch('pcbknowledge.v2.synthesis.validate_expansion')
    @patch('pcbknowledge.v2.synthesis.expand', return_value={'status': 'EXPANDED', 'checks': [], 'refusals': []})
    def test_parameters_and_ports_are_part_of_strict_structural_comparison(self, *_):
        for field, value in (('parameters', {'voltage': {'value': 9, 'unit': 'V'}}),
                             ('ports', [{'name': 'OUT', 'type': 'GROUND'}])):
            attempts = self.attempts()
            attempts[0]['graph']['instances'][0][field] = value
            attempts[0]['receipt']['graph_sha256'] = digest(attempts[0]['graph'])
            result = self.evaluate(attempts, reference=graph())
            self.assertFalse(result['attempts'][0]['structural_match'])
            self.assertTrue(result['attempts'][1]['structural_match'])
            self.assertEqual(result['attempts'][0]['structural_comparison'], 'COMPARED')
            self.assertEqual(result['attempts'][0]['reviewer_verdict'], 'EQUIVALENT')
            self.assertTrue(result['attempts'][0]['equivalence_review'])

    @patch('pcbknowledge.v2.synthesis.validate_expansion')
    @patch('pcbknowledge.v2.synthesis.expand', return_value={'status': 'EXPANDED', 'checks': [], 'refusals': []})
    def test_repeated_identical_blocks_never_collapse_swapped_connectivity_to_match(self, *_):
        reference = graph()
        duplicate = copy.deepcopy(reference['instances'][1])
        duplicate['id'] = 'other-load'
        reference['instances'].append(duplicate)
        attempts = self.attempts()
        for index, attempt in enumerate(attempts):
            modified = copy.deepcopy(reference)
            modified['id'] = 'duplicate-attempt-' + str(index)
            modified['connections'][0]['endpoints'][1]['instance'] = 'other-load'
            attempt['graph'] = modified
            attempt['receipt']['graph_sha256'] = digest(modified)
        result = self.evaluate(attempts, reference=reference)
        self.assertTrue(all(not row['structural_match'] for row in result['attempts']))
        self.assertTrue(all(row['structural_comparison'] == 'AMBIGUOUS_REPEATED_SIGNATURE'
                            for row in result['attempts']))
        # Ambiguity may be accepted only by the independent, explicit positive review.
        for attempt in attempts:
            attempt['receipt']['reviewer_verdict'] = 'NOT_EQUIVALENT'
        self.assertEqual(self.evaluate(attempts, reference=reference)['passed'], 0)
