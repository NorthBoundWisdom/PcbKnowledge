"""Preserved G3 query-mediated attempts and explicit current-engine regression replay."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.bundle import Bundle, build_bundle
from pcbknowledge.v2.synthesis import digest, replay_corpus
from pcbknowledge.v2.synthesis_evidence import load_attempt
from pcbknowledge.v2.synthesis_inputs import resolve_replay_inputs

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / 'evals/synthesis/g3'


class G3SynthesisTests(unittest.TestCase):
    corpus = CORPUS

    @classmethod
    def setUpClass(cls):
        cls.snapshot = read_json((cls.corpus / 'input.json').read_bytes())
        cls.attempts = [load_attempt(ROOT, cls.corpus / (name + '.json'), recover_history=True)
                        for name in ('one', 'two', 'three')]
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        base = Path(cls.temp.name).resolve()
        clone = base / 'original-input'
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'clone', '--shared', '--no-checkout',
                        str(ROOT), str(clone)], check=True, capture_output=True)
        for arguments in (('config', 'core.autocrlf', 'false'),
                          ('checkout', '--detach', cls.snapshot['bundle_commit'])):
            subprocess.run(['git', '-C', str(clone), *arguments], check=True, capture_output=True)
        cls.path = build_bundle(clone, base / 'bundle')
        document = resolve_replay_inputs(cls.snapshot, cls.path)
        cls.bundle = Bundle.from_document(document)
        cls.addClassCleanup(cls.bundle.close)

    def test_original_content_replays_with_explicit_current_engine_identity(self):
        reference = read_json((self.bundle.catalog.root / 'evals/golden-designs/g3.block-graph.json').read_bytes())
        result = replay_corpus(
            self.bundle, 'G3', self.attempts, reference,
            orchestrator=self.attempts[0]['receipt']['orchestrator'],
            skill_text=self.snapshot['skill_text'], bundle_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),
        )
        self.assertEqual((result['status'], result['passed']), ('PASS', 3))
        self.assertEqual(result['receipt_identity'], 'CATALOG_CONTENT_REPLAY')
        self.assertEqual(result['input_identity'], self.snapshot['input_identity'])
        original = read_json((self.corpus / 'result.json').read_bytes())
        self.assertEqual(original['receipt_identity'], 'CATALOG_CONTENT')
        self.assertEqual(original['evaluation_engine_sha256'], self.snapshot['input_identity']['engine_sha256'])
        self.assertEqual((original['status'], original['passed']), ('PASS', 3))

    def test_packets_queries_submissions_and_independent_review_are_authentic(self):
        authors = {attempt['receipt']['agent'] for attempt in self.attempts}
        self.assertEqual(len(authors), 3)
        for attempt in self.attempts:
            receipt = attempt['receipt']
            packet = attempt['initial_packet']
            self.assertNotIn(receipt['reviewer'], authors | {receipt['orchestrator']})
            self.assertEqual(receipt['initial_packet_sha256'], digest(packet))
            self.assertEqual(receipt['transcript_sha256'], digest(attempt['transcript']))
            self.assertEqual(receipt['graph_sha256'], digest(attempt['graph']))
            self.assertEqual(packet['input_hashes']['input_identity'], self.snapshot['input_identity'])
            self.assertEqual(packet['brief'], self.bundle.briefs['G3'])
            self.assertEqual(packet['skill_text'], self.snapshot['skill_text'])
            submitted = []
            for submission in attempt['submissions']:
                raw = submission['original_utf8'].encode('utf-8')
                self.assertEqual(hashlib.sha256(raw).hexdigest(), submission['original_sha256'])
                self.assertEqual(read_json(raw), submission['graph'])
                self.assertEqual(digest(submission['graph']), submission['graph_sha256'])
                submitted.append(submission['graph'])
            self.assertIn(attempt['graph'], submitted)
            validations = [row['response'] for row in attempt['transcript'] if row['query']['op'] == 'validate']
            self.assertTrue(validations)
            self.assertEqual(attempt['independent_review']['verdict'], 'EQUIVALENT')
