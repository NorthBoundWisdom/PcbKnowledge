"""Replay three original T5 graphs; full query evidence remains an explicit local cache."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from pcbknowledge.serialization import canonical_json, read_json
from pcbknowledge.v2.bundle import Bundle, build_bundle
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.coverage import coverage_all
from pcbknowledge.v2.expansion import expand, validate_expansion
from pcbknowledge.v2.synthesis import digest
from pcbknowledge.v2.synthesis_cache import validate_descriptor
from pcbknowledge.v2.synthesis_evidence import load_attempt
from pcbknowledge.v2.synthesis_inputs import resolve_replay_inputs

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / 'evals/synthesis/t5'


class T5SynthesisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = read_json((ARCHIVE / 'input.json').read_bytes())
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
        skill = subprocess.check_output(['git', '-C', str(clone), 'show',
                                         'HEAD:.codex/skills/synthesize-block-graph/SKILL.md'])
        if hashlib.sha256(skill).hexdigest() != cls.snapshot['skill_sha256']:
            raise ValueError('Original committed skill differs from input metadata')
        replay = {**cls.snapshot, 'format': 'pcbknowledge.synthesis-input.v2',
                  'skill_text': skill.decode('utf-8')}
        cls.bundle = Bundle.from_document(resolve_replay_inputs(replay, path))
        cls.addClassCleanup(cls.bundle.close)

    def test_committed_summaries_contain_metadata_not_full_evidence(self):
        self.assertEqual(self.snapshot['format'], 'pcbknowledge.synthesis-input-metadata.v1')
        self.assertEqual(set(self.snapshot), {'format', 'brief', 'brief_sha256', 'bundle_commit',
                                             'bundle_sha256', 'input_identity', 'skill_sha256'})
        result = read_json((ARCHIVE / 'result.json').read_bytes())
        self.assertEqual(result['format'], 'pcbknowledge.synthesis-result-metadata.v1')
        self.assertEqual(len(result['full_report_sha256']), 64)
        for row in result['attempts']:
            self.assertEqual(set(row), {'agent', 'graph_sha256', 'status', 'checks', 'a2',
                                        'reviewer_verdict', 'reference_equivalent', 'structural_match'})

    def test_metadata_preserves_three_authors_and_scored_failed_revision(self):
        authors, reviewers = set(), set()
        for name in ('one', 'two', 'three'):
            path = ARCHIVE / (name + '.json')
            document = read_json(path.read_bytes())
            descriptor = validate_descriptor(document)
            self.assertLessEqual(path.stat().st_size, 30_000)
            receipt = document['receipt']
            for key in ('bundle_commit', 'bundle_sha256', 'brief_sha256', 'skill_sha256', 'input_identity'):
                self.assertEqual(receipt[key], self.snapshot[key])
            self.assertEqual(receipt['graph_sha256'], digest(document['graph']))
            self.assertEqual(receipt['reviewer_verdict'], 'NOT_EQUIVALENT' if name == 'two' else 'EQUIVALENT')
            if name == 'two':
                self.assertEqual(len(descriptor['submission_hashes']), 3)
                self.assertEqual(receipt['graph_sha256'], descriptor['submission_hashes'][1]['graph_sha256'])
            authors.add(receipt['agent'])
            reviewers.add(receipt['reviewer'])
        self.assertEqual(len(authors), 3)
        self.assertFalse(authors & reviewers)
        result = read_json((ARCHIVE / 'result.json').read_bytes())
        self.assertEqual((result['status'], result['passed'], result['total'], result['required']), ('PASS', 2, 3, 2))
        self.assertEqual(result['input_identity'], self.snapshot['input_identity'])

    def test_original_graphs_replay_two_passes_and_one_typed_refusal(self):
        for name in ('one', 'two', 'three'):
            graph = read_json((ARCHIVE / (name + '.json')).read_bytes())['graph']
            intent = expand(self.bundle.catalog, graph, self.bundle.briefs['T5'], bundle_commit=self.bundle.commit)
            if name == 'two':
                self.assertEqual(intent['status'], 'REFUSED')
                self.assertTrue(any(row['code'] == 'INVALID_REFERENCE' and row['path'] == 'graph'
                                    and 'configuration mode' in row['reason'] for row in intent['refusals']))
            else:
                validate_expansion(self.bundle, intent, graph)
                self.assertEqual(intent['status'], 'EXPANDED', intent['refusals'])
                self.assertEqual(len(intent['checks']), 107)
                self.assertTrue(all(row['result'] == 'PASS' for row in intent['checks']))

    def test_aggregate_coverage_preserves_the_failed_archived_attempt(self):
        catalog = Catalog(ROOT, ROOT / 'schemas')
        report = coverage_all(catalog)
        row = next(item for item in report['briefs'] if item['brief'] == 'T5')
        self.assertEqual(row['status'], 'INCOMPLETE')
        self.assertEqual(row['graph_readiness'], 'REFUSED')
        self.assertTrue(any(item['code'] == 'INVALID_REFERENCE' and 'configuration mode' in item['reason']
                            for item in row['graph_refusals']))
        self.assertTrue(any(graph['status'] == 'EXPANDED' for graph in row['graphs']))

    def test_missing_query_cache_is_not_full_evidence_replay(self):
        for name in ('one', 'two', 'three'):
            document = read_json((ARCHIVE / (name + '.json')).read_bytes())
            with self.subTest(attempt=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'attempt.json'
                path.write_text(canonical_json(document), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'NOT_LOCALLY_VERIFIED'):
                    load_attempt(Path(directory), path, recover_history=True)
