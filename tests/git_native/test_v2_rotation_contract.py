"""Global pad angles and native parse ordering start from the actual emitter."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from pcbknowledge.v2.boardview import board_from_text, children, field
from pcbknowledge.v2.handoff import _footprint, _syntax
from pcbknowledge.v2.placement import apply_positions
from pcbknowledge.v2.sexpr import dumps


class RotationContractTests(unittest.TestCase):
    def emitted(self):
        package = ('(footprint "synthetic" (version 20241229) (layer "F.Cu") '
                   '(pad "1" smd rect (at 2 3 30) (size 1 2) (layers "F.Cu")))')
        component = {'ref': 'U1', 'package': 'package:test', 'footprint': 'test:part'}
        class Catalog:
            def get(self, *args):
                return {}
        with patch('pcbknowledge.v2.handoff.export_kicad', return_value=package):
            return _footprint({'id': 'test', 'brief_id': 'test', 'bundle_commit': 'a' * 40},
                              component, Catalog(), (10, 10), {})

    def test_emitter_and_rigid_transform_keep_global_angles_before_pads(self):
        footprint = self.emitted()
        tree = ['kicad_pcb', ['net', '0', ''], footprint]
        original = deepcopy(tree)
        for rotation in (0, 90, 180, 270):
            with self.subTest(rotation=rotation):
                result = apply_positions(tree, {'U1': (12, 15, rotation)})
                fp = children(result, 'footprint')[0]
                tags = [node[0] for node in fp if isinstance(node, list)]
                self.assertLess(tags.index('at'), tags.index('pad'))
                pad = children(fp, 'pad')[0]
                self.assertEqual(list(map(float, field(pad, 'at'))), [2, 3, (rotation + 30) % 360])
                self.assertEqual(field(pad, 'size'), ['1', '2'])
                actual = board_from_text(dumps(_syntax(result)))['footprints']['U1']['pads']['1'][0]
                centers = {0: [14, 18], 90: [15, 13], 180: [10, 12], 270: [9, 17]}
                self.assertEqual(actual['at'], centers[rotation])
                self.assertEqual(actual['rotation'], (rotation + 30) % 360)
                self.assertEqual(actual['size'], [1, 2])
                self.assertEqual(result, apply_positions(result, {'U1': (12, 15, rotation)}))
        self.assertEqual(tree, original)

    def test_late_transform_is_rejected_instead_of_silently_misread(self):
        fp = self.emitted()
        at = children(fp, 'at')[0]
        fp.remove(at)
        fp.append(at)
        tree = ['kicad_pcb', ['net', '0', ''], fp]
        with self.assertRaisesRegex(ValueError, 'transform must precede'):
            board_from_text(dumps(_syntax(tree)))
