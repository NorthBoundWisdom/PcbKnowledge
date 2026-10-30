"""Original derived-project tests, without claiming a placed or routed board."""
import copy
import csv
from io import StringIO
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand
from pcbknowledge.v2.footprints import derive_footprint
from pcbknowledge.v2.handoff import export_handoff, board_tree, _mount_positions, assembly_csv
from pcbknowledge.v2.handoff_rules import export_rules, project_settings
from pcbknowledge.v2.sexpr import parse

ROOT = Path(__file__).resolve().parents[2]


def nodes(tree, name):
    return [node for node in tree if isinstance(node, list) and node[0] == name]


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT, ROOT / 'schemas')
        self.graph = read_json((ROOT / 'evals/golden-designs/g1.block-graph.json').read_bytes())
        brief = read_json((ROOT / 'evals/golden-designs/g1.brief.json').read_bytes())
        # Pure projection fixture; production CLI supplies an authenticated Bundle.
        self.bundle = SimpleNamespace(catalog=self.catalog, commit='a' * 40, briefs={brief['id']: brief})
        self.intent = expand(self.catalog, self.graph, brief, bundle_commit=self.bundle.commit)
        self.assertEqual(self.intent['status'], 'EXPANDED', self.intent['refusals'])

    def test_repeatable_project_and_exact_net_pad_coverage(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve() / 'handoff'
            export_handoff(self.intent, self.bundle, self.graph, output)
            first = {p.relative_to(output): p.read_bytes() for p in output.rglob('*') if p.is_file()}
            export_handoff(self.intent, self.bundle, self.graph, output)
            self.assertEqual(first, {p.relative_to(output): p.read_bytes() for p in output.rglob('*') if p.is_file()})
            board = parse((output / 'design.kicad_pcb').read_text())
            footprints = nodes(board, 'footprint')
            self.assertEqual(len(footprints), len(self.intent['components']))
            actual = {}
            components = {c['ref']: c for c in self.intent['components']}
            for fp in footprints:
                ref = next(p[2] for p in nodes(fp, 'property') if p[1] == 'Reference')
                pads = nodes(fp, 'pad')
                package = self.catalog.get(components[ref]['package'])
                expected = derive_footprint(package)['pads']
                self.assertEqual({p[1] for p in pads}, {p['number'] for p in expected})
                for pad in pads:
                    for net in nodes(pad, 'net'):
                        actual[ref, pad[1]] = net[2]
            expected = {(p['ref'], p['pin']): n['name'] for n in self.intent['nets'] for p in n['pins']}
            self.assertEqual(actual, expected)
            self.assertEqual(nodes(board, 'segment'), [])
            self.assertEqual(nodes(board, 'via'), [])

    def test_outline_mounts_and_all_other_courtyards_are_parked(self):
        board = board_tree(self.intent, self.catalog)
        self.assertEqual(nodes(nodes(board, 'gr_rect')[0], 'end')[0][1:], ['50', '50'])
        mounts = _mount_positions(self.intent, 50, 50)
        self.assertEqual(set(mounts.values()), {(3.5, 3.5), (46.5, 3.5), (3.5, 46.5), (46.5, 46.5)})
        components = {c['ref']: c for c in self.intent['components']}
        for fp in nodes(board, 'footprint'):
            ref = next(p[2] for p in nodes(fp, 'property') if p[1] == 'Reference')
            x, y = map(float, nodes(fp, 'at')[0][1:])
            if ref in mounts:
                self.assertEqual((x, y), mounts[ref])
            else:
                package = self.catalog.get(components[ref]['package'])
                self.assertGreater(x + derive_footprint(package)['courtyard']['min_x'], 50)

    def test_each_manufacturing_rule_and_netclass_preserves_inputs(self):
        rules = export_rules(self.intent, self.catalog)
        for constraint, value in [('track_width', '.150000'), ('clearance', '.150000'),
                                  ('hole_size', '.300000'), ('annular_width', '.250000')]:
            self.assertIn(f'(constraint {constraint} (min 0{value}mm))', rules)
        self.assertIn('(constraint track_width (min 0.300000mm))', rules)
        self.assertIn("A.NetName == 'USB_VBUS'", rules)
        self.assertEqual(rules.count('(rule "hole-edge:'), 4)
        self.assertIn('(constraint edge_clearance (min 1.900000mm))', rules)
        project = project_settings(self.intent, self.catalog)
        classes = {c['name']: c for c in project['net_settings']['classes']}
        assignments = {p['pattern']: p['netclass'] for p in project['net_settings']['netclass_patterns']}
        self.assertEqual(classes[assignments['USB_VBUS']]['track_width'], .3)
        self.assertEqual(set(assignments), {n['name'] for n in self.intent['nets']})

    def test_g1_conductive_holes_meet_unchanged_fab_drill_and_annulus(self):
        fab = self.catalog.get(self.intent['fab_profile'])
        drill_floor = fab['drill_min']['value']
        ring_floor = fab['annular_ring_min']['value']
        count = 0
        for component in self.intent['components']:
            package = self.catalog.get(component['package'])
            for pad in derive_footprint(package)['pads']:
                if pad['kind'] != 'THROUGH_HOLE':
                    continue
                count += 1
                dx = pad.get('drill', pad.get('drill_width'))
                dy = pad.get('drill', pad.get('drill_height'))
                self.assertIsNotNone(dx)
                self.assertIsNotNone(dy)
                label = (component['ref'], pad['number'])
                self.assertGreaterEqual(min(dx, dy) + 1e-9, drill_floor, label)
                ring = min(pad['width'] - dx, pad['height'] - dy) / 2
                self.assertGreaterEqual(ring + 1e-9, ring_floor, label)
        self.assertGreater(count, 0)

    def test_rule_inputs_cannot_be_unknown_or_wrong_units(self):
        fab = self.catalog.get(self.intent['fab_profile'])
        for key in ('trace_width_min', 'clearance_min', 'drill_min', 'annular_ring_min'):
            original = copy.deepcopy(fab[key])
            for broken in ({'status': 'UNKNOWN'}, {'unit': 'mil', 'value': 10}, {'unit': 'mm', 'value': -1}):
                fab[key] = broken
                with self.assertRaises(ValueError):
                    export_rules(self.intent, self.catalog)
            fab[key] = original
        changed = copy.deepcopy(self.intent)
        constraint = next(c for c in changed['layout'] if c['kind'] == 'NET_WIDTH_MIN')
        constraint['min_width']['value'] = 2.25
        self.assertIn('(constraint track_width (min 2.250000mm))', export_rules(changed, self.catalog))
        constraint['min_width'] = {'status': 'UNKNOWN'}
        with self.assertRaises(ValueError):
            export_rules(changed, self.catalog)

    def test_assembly_csv_all_references_and_tamper_refusal_before_writes(self):
        rows = list(csv.DictReader(StringIO(assembly_csv(self.intent, self.catalog))))
        self.assertEqual(sum(int(row['quantity']) for row in rows), len(self.intent['components']))
        self.assertTrue(any(row['mount_type'] == 'THT' and row['assembly_method'] == 'HAND_SOLDER' for row in rows))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve() / 'output'
            changed = copy.deepcopy(self.intent)
            changed['nets'][0]['name'] = 'forged'
            with self.assertRaisesRegex(ValueError, 'differs'):
                export_handoff(changed, self.bundle, self.graph, output)
            self.assertFalse(output.exists())

    def test_conflicting_mounts_and_unsafe_targets_refuse(self):
        changed = copy.deepcopy(self.intent)
        item = copy.deepcopy(next(c for c in changed['layout'] if c['kind'] == 'EDGE_DISTANCE'))
        item['distance']['value'] += 1
        changed['layout'].append(item)
        with self.assertRaisesRegex(ValueError, 'Incompatible edge constraints for mounting_H1 on width'):
            board_tree(changed, self.catalog)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve()
            (output / 'assembly.csv').mkdir()
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                export_handoff(self.intent, self.bundle, self.graph, output)
            self.assertFalse((output / 'design.kicad_pcb').exists())
