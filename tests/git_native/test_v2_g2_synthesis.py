"""Preserved G2 query-mediated attempts and explicit current-engine regression replay."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from pcbknowledge.serialization import read_json
from tests.git_native.crystal_projection import assert_reviewed_g2_projection
from pcbknowledge.v2.bundle import Bundle, build_bundle
from pcbknowledge.v2.synthesis import digest, replay_corpus
from pcbknowledge.v2.synthesis_evidence import load_attempt
from pcbknowledge.v2.synthesis_inputs import resolve_replay_inputs

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / 'evals/synthesis/g2-round1'


class G2SynthesisTests(unittest.TestCase):
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
        reference = read_json((self.bundle.catalog.root / 'evals/golden-designs/g2.block-graph.json').read_bytes())
        result = replay_corpus(
            self.bundle, 'G2', self.attempts, reference,
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
            self.assertEqual(packet['brief'], self.bundle.briefs['G2'])
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


class FinalG2SynthesisTests(G2SynthesisTests):
    corpus = ROOT / 'evals/synthesis/g2'

    def test_unchanged_graphs_against_current_catalog_are_separate_regressions(self):
        from pcbknowledge.v2.catalog import Catalog
        from pcbknowledge.v2.expansion import expand
        catalog = Catalog(ROOT, ROOT / 'schemas')
        brief = read_json((ROOT / 'evals/golden-designs/g2.brief.json').read_bytes())
        for attempt in self.attempts:
            graph = attempt['graph']
            current = expand(catalog, graph, brief, bundle_commit='0' * 40)
            self.assertEqual(current['status'], 'EXPANDED', current['refusals'])
            original = [row['response']['intent'] for row in attempt['transcript']
                        if row['query']['op'] == 'validate'][-1]
            assert_reviewed_g2_projection(self, original, current, catalog)
            self.assertEqual(digest(graph), attempt['receipt']['graph_sha256'])
            self.assertEqual(len(current['checks']), 106)
            fuses = {c['ref'] for c in current['components'] if c['part'] == 'part:littelfuse-0451001-mrl'}
            self.assertEqual(len(fuses), 1)
            constraints = [c for c in current['layout'] if c['kind'] == 'PLACE_NEAR'
                           and c['subject'] == next(iter(fuses)) + '.pin:1']
            self.assertEqual(len(constraints), 1)
            self.assertEqual(constraints[0]['max_distance']['value'], 5)

    def test_reviewed_crystal_projection_rejects_unrelated_or_incomplete_changes(self):
        import copy
        from pcbknowledge.v2.catalog import Catalog
        from pcbknowledge.v2.expansion import expand
        catalog = Catalog(ROOT, ROOT / 'schemas')
        attempt = self.attempts[0]
        original = [row['response']['intent'] for row in attempt['transcript']
                    if row['query']['op'] == 'validate'][-1]
        original_hash = digest(original)
        brief = read_json((ROOT / 'evals/golden-designs/g2.brief.json').read_bytes())
        current = expand(catalog, attempt['graph'], brief, bundle_commit='0' * 40)
        crystal = next(c['ref'] for c in current['components'] if c['part'] == 'part:abracon-abmm2-8-18')
        for mutation in ('signal', 'ground', 'check', 'loop', 'unrelated', 'evidence', 'scope_evidence'):
            forged = copy.deepcopy(current)
            if mutation in ('signal', 'ground'):
                pin = '3' if mutation == 'signal' else '4'
                net = next(n for n in forged['nets'] if {'ref': crystal, 'pin': pin} in n['pins'])
                net['pins'].remove({'ref': crystal, 'pin': pin})
            elif mutation == 'check':
                check = next(c for c in forged['checks'] if c['id'] == 'source:' + crystal + ':4')
                check['result'] = 'FAIL'
            elif mutation == 'loop':
                loop = next(c for c in forged['layout'] if crystal + '.pin:3' in c.get('path', []))
                loop['path'][2] = crystal + '.pin:2'
            elif mutation == 'unrelated':
                component = next(c for c in forged['components'] if c['ref'] != crystal)
                component['part'] = 'part:forged'
            elif mutation == 'scope_evidence':
                forged['evidence'] = [e for e in forged['evidence']
                                      if e['source'] != 'source:kemet-c0603c101j5gactu']
            else:
                evidence = next(e for e in forged['evidence'] if e['source'] == 'source:abracon-abmm2')
                evidence['page'] = 999
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                assert_reviewed_g2_projection(self, original, forged, catalog)
        self.assertEqual(digest(original), original_hash)
        self.assertEqual(digest(attempt['graph']), attempt['receipt']['graph_sha256'])

    def test_current_regression_retains_distinct_original_and_evaluation_identities(self):
        from pcbknowledge.v2.synthesis_identity import validate_identity
        report = read_json((self.corpus / 'current-catalog-regression.json').read_bytes())
        self.assertEqual(report['mode'], 'UNCHANGED_GRAPH_CURRENT_CATALOG')
        self.assertFalse(report['fresh_synthesis'])
        self.assertEqual((report['status'], report['passed']), ('PASS', 3))
        self.assertEqual(report['original_input_identity'], self.snapshot['input_identity'])
        validate_identity(report['evaluation_input_identity'])
        self.assertNotEqual(report['original_input_identity']['catalog_tree'],
                            report['evaluation_input_identity']['catalog_tree'])
        for row, attempt in zip(report['attempts'], self.attempts):
            self.assertEqual(row['graph_sha256'], digest(attempt['graph']))
            self.assertEqual(row['electrical_projection_sha256'], row['original_electrical_projection_sha256'])
            self.assertEqual((row['status'], row['checks'], row['refusals']), ('EXPANDED', 101, []))
