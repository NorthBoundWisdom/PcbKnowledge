"""Global pad angles and native parse ordering start from the actual emitter."""
import unittest
from unittest.mock import patch

from pcbknowledge.v2.boardview import board_from_text, children, field
from pcbknowledge.v2.handoff import _footprint, _syntax
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

    def test_emitter_and_native_rotation_fixtures_keep_global_angles(self):
        footprint = self.emitted()
        tags = [node[0] for node in footprint if isinstance(node, list)]
        self.assertLess(tags.index('at'), tags.index('pad'))
        self.assertEqual(field(children(footprint, 'pad')[0], 'at'), ['2', '3', '30'])
        cases = [(0, 30, [14, 18]), (90, 120, [15, 13]),
                 (180, 210, [10, 12]), (270, 300, [9, 17])]
        for rotation, pad_angle, center in cases:
            with self.subTest(rotation=rotation):
                text = ('(kicad_pcb (net 0 "") (footprint "synthetic" (layer "F.Cu") '
                        f'(at 12 15 {rotation}) (property "Reference" "U1") '
                        f'(pad "1" smd rect (at 2 3 {pad_angle}) (size 1 2) (layers "F.Cu"))))')
                actual = board_from_text(text)['footprints']['U1']['pads']['1'][0]
                self.assertEqual(actual['at'], center)
                self.assertEqual(actual['rotation'], pad_angle)
                self.assertEqual(actual['size'], [1, 2])

    def test_late_transform_is_rejected_instead_of_silently_misread(self):
        fp = self.emitted()
        at = children(fp, 'at')[0]
        fp.remove(at)
        fp.append(at)
        tree = ['kicad_pcb', ['net', '0', ''], fp]
        with self.assertRaisesRegex(ValueError, 'transform must precede'):
            board_from_text(dumps(_syntax(tree)))
