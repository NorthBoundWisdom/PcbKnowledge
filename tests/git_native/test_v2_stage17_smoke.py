"""One fresh skill smoke is preserved separately from three-author corpus acceptance."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.bundle import Bundle, build_bundle
from pcbknowledge.v2.bringup import make_bringup
from pcbknowledge.v2.expansion import expand, validate_expansion
from pcbknowledge.v2.synthesis import digest
from pcbknowledge.v2.synthesis_cache import validate_descriptor
from pcbknowledge.v2.synthesis_inputs import resolve_replay_inputs

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / 'evals/synthesis/stage17-smoke'


class Stage17SmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = read_json((CORPUS / 'input.json').read_bytes())
        cls.attempt = read_json((CORPUS / 'one.json').read_bytes())
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        base = Path(cls.temporary.name).resolve()
        clone = base / 'original-input'
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'clone', '--shared', '--no-checkout',
                        str(ROOT), str(clone)], check=True, capture_output=True)
        for args in (('config', 'core.autocrlf', 'false'),
                     ('checkout', '--detach', cls.snapshot['bundle_commit'])):
            subprocess.run(['git', '-C', str(clone), *args], check=True, capture_output=True)
        path = build_bundle(clone, base / 'bundle')
        cls.bundle = Bundle.from_document(resolve_replay_inputs(cls.snapshot, path))
        cls.addClassCleanup(cls.bundle.close)

    def test_small_receipt_binds_original_final_submission(self):
        descriptor = validate_descriptor(self.attempt)
        receipt = self.attempt['receipt']
        self.assertEqual(len(descriptor['submission_hashes']), 3)
        self.assertEqual(receipt['graph_sha256'], digest(self.attempt['graph']))
        self.assertEqual(receipt['input_identity'], self.snapshot['input_identity'])
        self.assertEqual(receipt['reviewer_verdict'], 'EQUIVALENT')
        self.assertEqual(self.attempt['scope'], 'SINGLE_SKILL_SMOKE')
        self.assertFalse(self.attempt['corpus_acceptance'])
        self.assertLessEqual((CORPUS / 'one.json').stat().st_size, 30_000)

    def test_frozen_graph_replays_original_catalog_without_evidence_cache(self):
        graph = self.attempt['graph']
        intent = expand(self.bundle.catalog, graph, self.bundle.briefs['G1'],
                        bundle_commit=self.bundle.commit)
        validate_expansion(self.bundle, intent, graph)
        self.assertEqual(intent['status'], 'EXPANDED', intent['refusals'])
        self.assertEqual(len(intent['checks']), 96)
        self.assertTrue(all(check['result'] == 'PASS' for check in intent['checks']))
        self.assertEqual((len(intent['components']), len(intent['nets'])), (46, 25))
        report = make_bringup(intent, graph, self.bundle.briefs['G1'], self.bundle.catalog)
        self.assertEqual(report['range_coverage'], 'UNKNOWN')
        self.assertTrue(all(rail['result'] == 'NOT_RUN' for rail in report['rails']))
