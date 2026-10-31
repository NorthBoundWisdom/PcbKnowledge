"""Current catalog readiness and canonical selection/expansion regression pins."""
import copy
import hashlib
from pathlib import Path
import unittest

from pcbknowledge.serialization import canonical_json, read_json
from pcbknowledge.v2.catalog import Catalog, selected_candidate
from pcbknowledge.v2.audit import design_inputs, require_audit
from pcbknowledge.v2.coverage import coverage, coverage_all
from pcbknowledge.v2.expansion import expand

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_HASHES = {
    't5': '47a92cd63892ede8edb164dd82f232b07a6c83da80137afda5b81c2032eebf3d',
    'g1': '55cbaeb975b794a5e61eb5faf47c87257317855ae95b872449ba100849a12ce8',
    'g1v1': 'd2299e2463daca5ffac626a23b15b4f37359985e7cd1b83c989ccfb0f4282973',
    'g1v2': '154a27a31d04a3ad08f3170033b46adef16022e1e8a2529e6cbb4e5c97d66ecf',
    'g2': '30d522f03e34296b1eb156a42912695a7112b6dc06aa0138c257fe8bc2e6a9f0',
    'g3': 'e4081cac68a671af983b7d4d26a0d9f54f6b8d6606b66767bac2a0aae3671ab2',
    'g4': '54e16127e3886ac83d8aa36bfba1de8ac109f0d29defe08ef6e68d724b54f857',
    'g5': 'cef6251444ab2cf0e4a23fc9cf67cbb0a5bc33c511e363d5febe430671405600',
}


class ReferenceBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(ROOT, ROOT/'schemas')

    def test_every_committed_positive_ready_and_t1_refused(self):
        require_audit(self.catalog)
        _, briefs = design_inputs(ROOT)
        paths = [*sorted((ROOT / 'evals/golden-designs').glob('*.block-graph.json')),
                 *sorted((ROOT / 'evals/corpus/themes').glob('*.block-graph.json'))]
        references = [read_json(path.read_bytes()) for path in paths]
        report = coverage_all(self.catalog, briefs, references)
        rows = {row['brief']: row for row in report['briefs']}
        positives = {identity for identity, row in rows.items() if row['status'] == 'READY'}
        self.assertEqual(positives, {name.upper() for name in REFERENCE_HASHES})
        for identity in sorted(positives):
            with self.subTest(brief=identity):
                self.assertEqual(rows[identity]['status'], 'READY', rows[identity])
                self.assertEqual(rows[identity]['blocks_ready'], rows[identity]['blocks_total'])
        self.assertEqual(rows['T1']['graph_readiness'], 'REFUSED')
        self.assertTrue(rows['T1']['graphs'])
        self.assertTrue(all(graph['status'] == 'REFUSED' for graph in rows['T1']['graphs']))

    def test_all_positive_reference_expansion_hashes(self):
        for name, expected in REFERENCE_HASHES.items():
            with self.subTest(reference=name):
                folder = 'golden-designs' if name.startswith('g') else 'corpus/themes'
                graph = read_json((ROOT/f'evals/{folder}/{name}.block-graph.json').read_bytes())
                brief = read_json((ROOT/f'evals/{folder}/{name}.brief.json').read_bytes())
                intent = expand(self.catalog, graph, brief, bundle_commit='a' * 40)
                self.assertEqual(intent['status'], 'EXPANDED', intent['refusals'])
                self.assertEqual(hashlib.sha256(canonical_json(intent).encode()).hexdigest(), expected)
                readiness = coverage(self.catalog, graph)
                chosen = {row['instance'] + '_' + ref: part for row in readiness['instances']
                          for ref, part in row['selected_parts'].items()}
                self.assertEqual(chosen, {part['ref']: part['part'] for part in intent['components']})

    def test_shared_selection_priority_and_tiebreak(self):
        choices = [{'id': 'part:a', 'verification': 'DRAFT'},
                   {'id': 'part:c', 'verification': 'AGENT_VERIFIED'},
                   {'id': 'part:b', 'verification': 'AGENT_VERIFIED'}]
        self.assertEqual(selected_candidate(choices)['id'], 'part:b')
        self.assertEqual(selected_candidate(list(reversed(choices)))['id'], 'part:b')
        choices.append({'id': 'part:z', 'verification': 'HUMAN_VERIFIED'})
        self.assertEqual(selected_candidate(choices)['id'], 'part:z')
        with self.assertRaises(ValueError):
            selected_candidate([])

    def test_unselected_draft_does_not_contaminate_selected_closure(self):
        catalog = copy.deepcopy(self.catalog)
        graph = read_json((ROOT/'evals/golden-designs/g1.block-graph.json').read_bytes())
        actual_candidates = catalog._candidates
        observed = []
        def with_draft(selection):
            choices = actual_candidates(selection)
            part = copy.deepcopy(selected_candidate(choices))
            part['id'], part['verification'] = 'part:synthetic-draft-alternative', 'DRAFT'
            part['package'] = 'package:unselected-unavailable'
            observed.append(part['id'])
            return [part, *choices]
        catalog._candidates = with_draft
        result = coverage(catalog, graph)
        self.assertEqual(result['status'], 'READY', result)
        self.assertTrue(observed)
        self.assertTrue(all('part:synthetic-draft-alternative' in ids for row in result['instances']
                            for ids in row['selections'].values()))
        self.assertTrue(all(part != 'part:synthetic-draft-alternative' for row in result['instances']
                            for part in row['selected_parts'].values()))

    def test_only_draft_selection_is_incomplete_and_expansion_refused(self):
        catalog = copy.deepcopy(self.catalog)
        graph = read_json((ROOT/'evals/golden-designs/g1.block-graph.json').read_bytes())
        brief = read_json((ROOT/'evals/golden-designs/g1.brief.json').read_bytes())
        for part in catalog.search('part'):
            part['verification'] = 'DRAFT'
        self.assertEqual(coverage(catalog, graph)['status'], 'INCOMPLETE')
        self.assertEqual(expand(catalog, graph, brief, bundle_commit='a' * 40)['status'], 'REFUSED')
