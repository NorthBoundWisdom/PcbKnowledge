"""Preserved first corpus-growth attempts, exact inputs and explicit regression replay."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.bundle import Bundle, build_bundle
from pcbknowledge.v2.synthesis import digest, replay_corpus
from pcbknowledge.v2.synthesis_inputs import resolve_replay_inputs

ROOT = Path(__file__).resolve().parents[2]



class PreservedCorpusMixin:

    @classmethod
    def setUpClass(cls):
        cls.corpus = ROOT / 'evals/synthesis' / cls.name
        cls.snapshot = read_json((cls.corpus / 'input.json').read_bytes())
        cls.attempts = [read_json((cls.corpus / (name + '.json')).read_bytes())
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
        negative = self.name.startswith('n')
        options = ({'expected_refusal': {'code': 'CHECK_FAILED', 'path': 'functions.rs485'}} if negative else
                   {'reference': read_json((self.bundle.catalog.root / 'evals/golden-designs' /
                                            (self.name + '.block-graph.json')).read_bytes())})
        result = replay_corpus(
            self.bundle, self.name.upper(), self.attempts, **options,
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
            key = 'refusal' if self.name.startswith('n') else 'graph'
            packet = attempt['initial_packet']
            self.assertNotIn(receipt['reviewer'], authors | {receipt['orchestrator']})
            self.assertEqual(receipt['initial_packet_sha256'], digest(packet))
            self.assertEqual(receipt['transcript_sha256'], digest(attempt['transcript']))
            self.assertEqual(receipt[key + '_sha256'], digest(attempt[key]))
            self.assertEqual(packet['input_hashes']['input_identity'], self.snapshot['input_identity'])
            self.assertEqual(packet['brief'], self.bundle.briefs[self.name.upper()])
            self.assertEqual(packet['skill_text'], self.snapshot['skill_text'])
            submitted = []
            for submission in attempt['submissions']:
                raw = submission['original_utf8'].encode('utf-8')
                self.assertEqual(hashlib.sha256(raw).hexdigest(), submission['original_sha256'])
                self.assertEqual(read_json(raw), submission[key])
                self.assertEqual(digest(submission[key]), submission[key + '_sha256'])
                submitted.append(submission[key])
            self.assertIn(attempt[key], submitted)
            validations = [row['response'] for row in attempt['transcript'] if row['query']['op'] in ('validate', 'submit_refusal')]
            self.assertTrue(validations)
            self.assertEqual(attempt['independent_review']['verdict'],
                             'CORRECT_REFUSAL' if key == 'refusal' else 'EQUIVALENT')


class G4SynthesisTests(PreservedCorpusMixin, unittest.TestCase):
    name = 'g4'


class G5SynthesisTests(PreservedCorpusMixin, unittest.TestCase):
    name = 'g5'


class N4SynthesisTests(PreservedCorpusMixin, unittest.TestCase):
    name = 'n4'


class CorpusCycleStopTests(unittest.TestCase):
    def test_successful_cycle_uses_no_new_blocks_and_all_nine_fresh_actors(self):
        report = read_json((ROOT / 'evals/synthesis/stage11-cycle1.json').read_bytes())
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['stop_reason'], 'NO_NEW_BLOCKS')
        self.assertEqual(report['new_block_ids'], [])
        actors = set()
        for name in ('g4', 'g5', 'n4'):
            folder = ROOT / 'evals/synthesis' / name
            result = read_json((folder / 'result.json').read_bytes())
            self.assertEqual((result['status'], result['passed'], result['total']), ('PASS', 3, 3))
            self.assertEqual(report['briefs'][name.upper()]['result_sha256'], digest(result))
            self.assertEqual(result['input_identity'], report['input_identity'])
            self.assertEqual(result['bundle_commit'], report['input_commit'])
            for actor in ('one', 'two', 'three'):
                attempt = read_json((folder / (actor + '.json')).read_bytes())
                actors.add(attempt['receipt']['agent'])
        self.assertEqual(len(actors), 9)
        def block_tree(commit):
            return subprocess.check_output(
                ['git', 'rev-parse', commit + ':knowledge/blocks'], cwd=ROOT,
            ).decode().strip()
        self.assertEqual(block_tree(report['input_commit']), block_tree(report['baseline_commit']))
        self.assertEqual(block_tree(report['input_commit']), report['block_subtree_sha'])
