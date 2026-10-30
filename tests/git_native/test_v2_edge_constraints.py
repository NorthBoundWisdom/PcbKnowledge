"""Synthetic edge feasibility at expansion and actual rectangular board dimensions."""
import copy
import unittest

from pcbknowledge.v2.edge_constraints import validate_edge_constraints
from pcbknowledge.v2.expansion import expand
from pcbknowledge.v2.intent import validate_intent
from tests.git_native import test_v2_bundle_expansion as expansion_fixtures
from tests.git_native.test_v2_record_contracts import quantity


def rule(edge, value, *, subject='R1', exact=False):
    return {'kind': 'EDGE_DISTANCE' if exact else 'EDGE_PLACEMENT', 'subject': subject,
            'edge': edge, 'distance' if exact else 'max_distance': quantity(value, 'mm')}


def envelope(width=80, length=100):
    return {'shape': 'RECTANGLE', 'max_width': quantity(width, 'mm'), 'max_length': quantity(length, 'mm')}


class EdgeConstraintTests(unittest.TestCase):
    def test_envelope_is_not_a_fixed_outline(self):
        rules = [rule('LEFT', 5), rule('RIGHT', 5)]
        validate_edge_constraints(rules, envelope())
        validate_edge_constraints(rules, envelope(), dimensions={'width': 10, 'length': 100})
        with self.assertRaisesRegex(ValueError, 'shared board width'):
            validate_edge_constraints(rules, envelope(), dimensions={'width': 80, 'length': 100})

    def test_actual_board_handoff_checks_both_edges(self):
        from pcbknowledge.v2.boardview import board_from_text
        from pcbknowledge.v2.layout import check_layout
        from tests.git_native.test_v2_layout import FixtureCatalog, board_text, intent
        handoff = intent()
        handoff['mechanical']['outline_envelope'] = envelope()
        handoff['layout'] = [rule('LEFT', 5, subject='A'), rule('RIGHT', 5, subject='A')]
        for width, expected in ((80, 'FAIL'), (10, 'PASS')):
            with self.subTest(width=width):
                text = board_text().replace('(at 2 2)', '(at 5 2)').replace('(end 20 20)', f'(end {width} 20)')
                report = check_layout(board_from_text(text), handoff, FixtureCatalog())
                self.assertEqual(report['result'], expected, report)
                self.assertEqual(report['checks'][1]['result'], 'PASS')
                self.assertEqual(report['checks'][2]['result'], expected)

    def test_axes_and_exact_boundaries(self):
        for near, far, axis, other in [('LEFT', 'RIGHT', 'width', 'length'),
                                       ('TOP', 'BOTTOM', 'length', 'width')]:
            with self.subTest(axis=axis):
                rules = [rule(near, 3), rule(far, 7)]
                validate_edge_constraints(rules, envelope(), dimensions={axis: 10, other: 20})
                with self.assertRaisesRegex(ValueError, 'shared board ' + axis):
                    validate_edge_constraints(rules, envelope(), dimensions={axis: 10.001, other: 20})

    def test_compatible_corner_and_distinct_subjects(self):
        rules = [rule('LEFT', 5), rule('TOP', 5), rule('RIGHT', 5, subject='R2')]
        validate_edge_constraints(rules, envelope(), dimensions={'width': 80, 'length': 100})
        # A pad is not its footprint origin and two different pads need not coincide.
        rules += [rule('RIGHT', 5, subject='R1.pin:1'), rule('RIGHT', 5, subject='R1.pin:2')]
        validate_edge_constraints(rules, envelope(), dimensions={'width': 80, 'length': 100})

    def test_same_edge_and_opposing_exact_distance_conflicts(self):
        for rules in ([rule('LEFT', 5), rule('LEFT', 6, exact=True)],
                      [rule('LEFT', 41, exact=True), rule('RIGHT', 41, exact=True)],
                      [rule('TOP', 51, exact=True), rule('BOTTOM', 51, exact=True)]):
            with self.subTest(rules=rules):
                with self.assertRaisesRegex(ValueError, 'Incompatible edge constraints'):
                    validate_edge_constraints(rules, envelope())
        validate_edge_constraints([rule('LEFT', 5), rule('LEFT', 5.01, exact=True)], envelope())
        validate_edge_constraints([rule('LEFT', 40.01, exact=True),
                                   rule('RIGHT', 40.01, exact=True)], envelope())

    def test_all_constraints_share_one_outline(self):
        rules = [rule('LEFT', 50), rule('LEFT', 5), rule('RIGHT', 5),
                 rule('LEFT', 11, subject='R2', exact=True)]
        with self.assertRaisesRegex(ValueError, 'shared board width'):
            validate_edge_constraints(rules, envelope())
        for ordered in (rules, list(reversed(rules))):
            with self.assertRaisesRegex(ValueError, 'shared board width'):
                validate_edge_constraints(ordered, envelope())

    def test_quantity_units_and_bounds(self):
        bounds = envelope()
        bounds['max_width'].pop('value')
        bounds['max_width']['max'] = 80
        bounds['max_width']['min'] = 60
        validate_edge_constraints([rule('LEFT', 5), rule('RIGHT', 5)], bounds)
        invalid = rule('LEFT', 5)
        for change in ({'unit': 'V'}, {'value': -1}, {'value': float('inf')}):
            mutated = copy.deepcopy(invalid)
            mutated['max_distance'].update(change)
            with self.assertRaises(ValueError):
                validate_edge_constraints([mutated], bounds)
        invalid['max_distance'].pop('value')
        invalid['max_distance']['max'] = 5
        with self.assertRaisesRegex(ValueError, 'resolved scalar'):
            validate_edge_constraints([invalid], bounds)

    def test_expansion_refuses_and_handoff_recomputes(self):
        catalog, graph, brief = expansion_fixtures.ExpansionTests().fixture()
        block = catalog.get('block:synthetic')
        block['layout'] = [rule('LEFT', 5)]
        original = expand(catalog, graph, brief, bundle_commit='a' * 40)
        self.assertEqual(original['status'], 'EXPANDED', original['refusals'])
        block['layout'].append(rule('LEFT', 6, exact=True))
        refused = expand(catalog, graph, brief, bundle_commit='a' * 40)
        self.assertEqual(refused['status'], 'REFUSED')
        self.assertTrue(any('Incompatible edge constraints' in r['reason'] for r in refused['refusals']))
        self.assertEqual(refused, expand(catalog, graph, brief, bundle_commit='a' * 40))
        for near, far in (('LEFT', 'RIGHT'), ('TOP', 'BOTTOM')):
            block['layout'] = [rule(near, 100, exact=True), rule(far, 100, exact=True)]
            refused = expand(catalog, graph, brief, bundle_commit='a' * 40)
            self.assertEqual(refused['status'], 'REFUSED')
            self.assertTrue(any('shared board' in r['reason'] for r in refused['refusals']))
        original['layout'].append(rule('LEFT', 6, subject='first_R1', exact=True))
        with self.assertRaisesRegex(ValueError, 'Incompatible edge constraints'):
            validate_intent(catalog, original, bundle_commit='a' * 40)

    def test_g2_export_checks_chosen_outline_before_writing(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        from pcbknowledge.serialization import read_json
        from pcbknowledge.v2.catalog import Catalog
        from pcbknowledge.v2.handoff import board_tree, export_handoff
        root = Path(__file__).resolve().parents[2]
        catalog = Catalog(root, root / 'schemas')
        graph = read_json((root / 'evals/golden-designs/g2.block-graph.json').read_bytes())
        brief = read_json((root / 'evals/golden-designs/g2.brief.json').read_bytes())
        corrected = expand(catalog, graph, brief, bundle_commit='a' * 40)
        self.assertEqual(corrected['status'], 'EXPANDED', corrected['refusals'])
        self.assertEqual(board_tree(corrected, catalog)[0], 'kicad_pcb')
        header = catalog.get('block:g2-power-input-header')
        edge = next(r for r in header['layout'] if r['kind'] == 'EDGE_PLACEMENT')
        edge['edge'] = 'LEFT'
        original = expand(catalog, graph, brief, bundle_commit='a' * 40)
        self.assertEqual(original['status'], 'EXPANDED', original['refusals'])
        constraints = [r for r in original['layout'] if r['kind'] == 'EDGE_PLACEMENT'
                       and r['subject'] == 'input_J1']
        self.assertEqual({r['edge'] for r in constraints}, {'LEFT', 'RIGHT'})
        with self.assertRaisesRegex(ValueError, 'shared board width'):
            board_tree(original, catalog)
        bundle = SimpleNamespace(catalog=catalog, briefs={brief['id']: brief}, commit='a' * 40)
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'handoff'
            with self.assertRaisesRegex(ValueError, 'shared board width'):
                export_handoff(original, bundle, graph, output)
            self.assertFalse(output.exists())
