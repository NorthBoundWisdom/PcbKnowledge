"""Audit fresh N6 receipt metadata; full transcript replay needs the local cache."""
import json
from pathlib import Path
import tempfile
import unittest

from pcbknowledge.serialization import canonical_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.requirements import assess_brief
from pcbknowledge.v2.synthesis import digest
from pcbknowledge.v2.synthesis_cache import validate_descriptor
from pcbknowledge.v2.synthesis_evidence import load_attempt

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / 'evals/synthesis/n6'


class N6SynthesisTests(unittest.TestCase):
    def test_receipt_metadata_and_current_refusal_contract(self):
        snapshot = json.loads((ARCHIVE / 'input.json').read_text(encoding='utf-8'))
        catalog = Catalog(ROOT, ROOT / 'schemas')
        brief = json.loads((ROOT / 'evals/corpus/themes/n6.brief.json').read_text(encoding='utf-8'))
        self.assertEqual(digest(brief), snapshot['brief_sha256'])
        current = assess_brief(catalog, brief)
        self.assertIn(('UNSATISFIED_SELECTION', 'functions.three_phase_drive'),
                      [(item['code'], item['path']) for item in current])
        authors = set()
        reviewers = set()
        for name in ('one', 'two', 'three'):
            path = ARCHIVE / (name + '.json')
            document = json.loads(path.read_text(encoding='utf-8'))
            validate_descriptor(document)
            self.assertLessEqual(path.stat().st_size, 30_000)
            receipt = document['receipt']
            for key in ('bundle_commit', 'bundle_sha256', 'brief_sha256', 'skill_sha256', 'input_identity'):
                self.assertEqual(receipt[key], snapshot[key])
            self.assertEqual(receipt['reviewer_verdict'], 'CORRECT_REFUSAL')
            self.assertEqual(receipt['mode'], 'QUERY_MEDIATED')
            self.assertIs(receipt['reference_accessed'], False)
            self.assertNotIn(receipt['orchestrator'], (receipt['agent'], receipt['reviewer']))
            refusal = document['refusal']
            self.assertEqual((refusal['brief'], refusal['code'], refusal['path']),
                             ('N6', 'UNSATISFIED_SELECTION', 'functions.three_phase_drive'))
            authors.add(receipt['agent'])
            reviewers.add(receipt['reviewer'])
        self.assertEqual(len(authors), 3)
        self.assertFalse(authors & reviewers)
        result = json.loads((ARCHIVE / 'result.json').read_text(encoding='utf-8'))
        self.assertEqual((result['status'], result['passed'], result['total']), ('PASS', 3, 3))
        self.assertEqual(result['input_identity'], snapshot['input_identity'])
        self.assertEqual(result['receipt_identity'], 'CATALOG_CONTENT')
        self.assertEqual(result['replayed_refusals'], current)
        self.assertTrue(all(item['correct_refusal'] for item in result['attempts']))
        self.assertEqual({item['agent'] for item in result['attempts']}, authors)

    def test_missing_original_cache_is_not_full_replay(self):
        for name in ('one', 'two', 'three'):
            document = json.loads((ARCHIVE / (name + '.json')).read_text(encoding='utf-8'))
            with self.subTest(attempt=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'attempt.json'
                path.write_text(canonical_json(document), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'NOT_LOCALLY_VERIFIED'):
                    load_attempt(Path(directory), path, recover_history=True)
