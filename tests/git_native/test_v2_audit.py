"""Reachability and manufacturer package-scope regressions."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from pcbknowledge.v2.audit import audit_catalog, design_inputs
from pcbknowledge.v2.catalog import Catalog
from tests.git_native.test_v2_record_contracts import fixtures


class AuditTests(unittest.TestCase):
    def fixture(self):
        records = {
            'block:used': {'id': 'block:used', 'components': [{'select': {'role': 'test'}}]},
            'part:first': {'id': 'part:first', 'package': 'package:shared'},
            'part:second': {'id': 'part:second', 'package': 'package:shared'},
            'package:shared': {'id': 'package:shared', 'evidence': [{'source': 'source:used', 'page': 1}]},
            'source:used': {'id': 'source:used'},
            'source:unused': {'id': 'source:unused'},
        }
        catalog = SimpleNamespace(
            records=records,
            get=lambda identity: records[identity],
            structure=lambda *_: None,
            _candidates=lambda _: [records['part:first'], records['part:second']],
        )
        graph = {'brief': 'G1', 'instances': [{'block': 'block:used'}]}
        return catalog, graph

    def test_role_selection_keeps_all_candidates_and_reports_orphan(self):
        catalog, graph = self.fixture()
        report = audit_catalog(catalog, [graph])
        self.assertEqual(report['unreachable'], ['source:unused'])
        self.assertIn('part:second', report['reachable'])
        del catalog.records['source:unused']
        self.assertEqual(audit_catalog(catalog, [graph])['status'], 'VALID')

    def test_missing_negative_block_cannot_hide_orphans(self):
        catalog, graph = self.fixture()
        graph['instances'][0]['block'] = 'block:missing'
        report = audit_catalog(catalog, [graph])
        self.assertEqual(report['reachable'], [])
        self.assertEqual(len(report['unreachable']), 5)

    def test_graph_discovery_reads_references_corpus_and_preserved_attempts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            directory = root / 'evals/corpus'
            directory.mkdir(parents=True)
            brief = {'schema': 'pcbknowledge.design-brief.v2', 'id': 'G1'}
            graph = {'schema': 'pcbknowledge.block-graph.v2', 'id': 'test', 'brief': 'G1', 'instances': []}
            (directory / 'brief.json').write_text(json.dumps(brief), encoding='utf-8')
            (directory / 'graph.json').write_text(json.dumps(graph), encoding='utf-8')
            (directory / 'attempt.json').write_text(json.dumps({'graph': graph}), encoding='utf-8')
            graphs, briefs = design_inputs(root)
            self.assertEqual(graphs, [graph, graph])
            self.assertEqual(briefs, {'G1': brief})
            (directory / 'linked.json').symlink_to(directory / 'graph.json')
            with self.assertRaisesRegex(ValueError, 'symlink'):
                design_inputs(root)


class PackageScopeTests(unittest.TestCase):
    def fixture(self):
        documents = fixtures()
        catalog = Catalog.__new__(Catalog)
        catalog.records = {documents[k]['id']: documents[k] for k in ('package', 'part')}
        return catalog, documents

    def test_explicit_mpn_scope_is_required_for_part(self):
        catalog, documents = self.fixture()
        catalog._part(documents['part'])
        changed = copy.deepcopy(documents['part'])
        changed['mpn'] = 'SIMILAR-BUT-NOT-COVERED'
        with self.assertRaisesRegex(ValueError, 'outside package drawing scope'):
            catalog._part(changed)

    def test_default_scope_cannot_replace_manufacturer_evidence(self):
        catalog, documents = self.fixture()
        documents['package']['scope'] = {
            'basis': 'ENGINEERING_DEFAULT', 'mpns': ['SYNTH-1'], 'note': 'Invented electrical scope.'
        }
        with self.assertRaisesRegex(ValueError, 'mechanical-only'):
            catalog._part(documents['part'])

    def test_scope_cites_the_exact_part_identity_source(self):
        catalog, documents = self.fixture()
        documents['package']['scope']['evidence'] = [{'source': 'source:unrelated', 'page': 1}]
        with self.assertRaisesRegex(ValueError, 'part identity source'):
            catalog._part(documents['part'])
