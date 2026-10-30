"""Replay preserved Stage 8 attempts against their exact original authenticated inputs."""
import hashlib
from pathlib import Path
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.bundle import Bundle
from pcbknowledge.v2.synthesis import digest, evaluate_historical_corpus
from pcbknowledge.v2.synthesis_inputs import reconstruct_bundle

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / 'evals/synthesis'
BRIEFS = ('G1V1', 'G1V2', 'N1', 'N2', 'N3')


class PreservedCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = read_json((CORPUS / 'stage8-input.json').read_bytes())
        cls.bundle = Bundle.from_document(reconstruct_bundle(ROOT, cls.snapshot))
        cls.addClassCleanup(cls.bundle.close)
        cls.attempts = {
            brief: [read_json((CORPUS / brief.lower() / (name + '.json')).read_bytes())
                    for name in ('one', 'two', 'three')]
            for brief in BRIEFS
        }

    def test_all_five_preserved_benchmarks_replay_three_of_three(self):
        original_root = self.bundle.catalog.root
        expectations = read_json((original_root / 'evals/corpus-expectations.json').read_bytes())
        for brief in BRIEFS:
            with self.subTest(brief=brief):
                attempts = self.attempts[brief]
                expected = expectations[brief]
                reference = None
                refusal = None
                if expected['outcome'] == 'SUPPORTED':
                    path = original_root / 'evals/golden-designs' / (brief.lower() + '.block-graph.json')
                    reference = read_json(path.read_bytes())
                else:
                    self.assertEqual(expected['outcome'], 'REFUSED')
                    refusal = expected['refusal']
                result = evaluate_historical_corpus(
                    self.bundle, brief, attempts, reference, refusal,
                    orchestrator=attempts[0]['receipt']['orchestrator'],
                    skill_text=self.snapshot['skill_text'], bundle_sha256=self.snapshot['bundle_sha256'],
                )
                self.assertEqual((result['status'], result['passed'], result['total']), ('PASS', 3, 3))
                historical = read_json((CORPUS / brief.lower() / 'result.json').read_bytes())
                self.assertEqual((historical['status'], historical['passed'], historical['total']), ('PASS', 3, 3))
                # Current diagnostics may grow; original hashes and acceptance inputs must not change.
                self.assertEqual(result['bundle_commit'], self.snapshot['bundle_commit'])

    def test_original_packets_submissions_and_actor_independence_are_preserved(self):
        authors, reviewers, orchestrators = set(), set(), set()
        skill = self.snapshot['skill_text']
        self.assertEqual(hashlib.sha256(skill.encode('utf-8')).hexdigest(), self.snapshot['skill_sha256'])
        for brief, attempts in self.attempts.items():
            for attempt in attempts:
                receipt = attempt['receipt']
                actor = receipt['agent']
                self.assertNotIn(actor, authors)
                authors.add(actor)
                reviewers.add(receipt['reviewer'])
                orchestrators.add(receipt['orchestrator'])
                packet = attempt['initial_packet']
                self.assertEqual(digest(packet), receipt['initial_packet_sha256'])
                self.assertEqual(packet['skill_text'], skill)
                self.assertEqual(packet['brief'], self.bundle.briefs[brief])
                self.assertEqual(packet['brief_sha256'], digest(self.bundle.briefs[brief]))
                for key in ('bundle_commit', 'bundle_sha256', 'skill_sha256'):
                    self.assertEqual(packet['input_hashes'][key], self.snapshot[key])
                output = attempt.get('graph', attempt.get('refusal'))
                submissions = attempt['submissions']
                self.assertTrue(submissions)
                preserved_outputs = []
                for submission in submissions:
                    payload = submission['original_utf8'].encode('utf-8')
                    self.assertEqual(hashlib.sha256(payload).hexdigest(), submission['raw_sha256'])
                    preserved_outputs.append(read_json(payload))
                self.assertIn(output, preserved_outputs)
        self.assertEqual(len(authors), 15)
        self.assertFalse(authors & reviewers)
        self.assertFalse(authors & orchestrators)
        self.assertFalse(reviewers & orchestrators)
