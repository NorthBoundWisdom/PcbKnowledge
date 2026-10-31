"""Routing sequence refuses source mutations and stale derived artifacts."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pcbknowledge.v2.routing import input_fingerprints, route_board, unchanged_placement


class RoutingTests(unittest.TestCase):
    def test_source_hashes_preserved_and_mutation_is_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            board = root / 'build/source.kicad_pcb'
            board.parent.mkdir()
            for suffix in ('.kicad_pcb', '.kicad_pro', '.kicad_dru'):
                board.with_suffix(suffix).write_text('original')
            before = input_fingerprints(board)
            with patch('pcbknowledge.v2.routing._route', return_value='NOT_RUN'):
                result = route_board(board, root / 'build/attempt', {}, None, {}, root=root)
            self.assertEqual(result['status'], 'NOT_RUN')
            self.assertEqual(input_fingerprints(board), before)
            def mutate(*args):
                board.write_text('changed')
                return 'PASS'
            with patch('pcbknowledge.v2.routing._route', side_effect=mutate):
                result = route_board(board, root / 'build/attempt2', {}, None, {}, root=root)
            self.assertEqual(result['status'], 'FAIL')
            self.assertIn('modified original', result['reason'])
            with self.assertRaises(ValueError):
                route_board(board, root / 'build/attempt2', {}, None, {}, root=root)

    def test_native_layer_order_and_nanometer_roundtrip_not_identity_change(self):
        before = {'nets': {'1': 'GND'}, 'outline': {}, 'footprints': {'U1': {
            'at': [1.00000000001, 2], 'pads': {'1': [{'layers': ['F.Cu', 'F.Paste', 'F.Mask']}]}}}}
        after = deepcopy(before)
        after['footprints']['U1']['at'][0] = 1.0
        after['footprints']['U1']['pads']['1'][0]['layers'].reverse()
        with patch('pcbknowledge.v2.routing.parse_board', side_effect=[before, after]):
            self.assertEqual(unchanged_placement('a', 'b')['status'], 'PASS')
        after['footprints']['U1']['at'][0] = 1.01
        with patch('pcbknowledge.v2.routing.parse_board', side_effect=[before, after]), self.assertRaises(ValueError):
            unchanged_placement('a', 'b')

    def test_signed_native_rotation_is_equivalent_but_different_orientation_fails(self):
        before = {"nets": {}, "outline": {}, "footprints": {"R1": {"rotation": 270.0}}}
        after = deepcopy(before)
        after["footprints"]["R1"]["rotation"] = -90.0
        with patch("pcbknowledge.v2.routing.parse_board", side_effect=[before, after]):
            self.assertEqual(unchanged_placement("a", "b")["status"], "PASS")
        before["footprints"]["R1"]["pads"] = {"1": [{"rotation": 360.0}]}
        after["footprints"]["R1"]["pads"] = {"1": [{"rotation": 0.0}]}
        with patch("pcbknowledge.v2.routing.parse_board", side_effect=[before, after]):
            self.assertEqual(unchanged_placement("a", "b")["status"], "PASS")
        after["footprints"]["R1"]["rotation"] = -89.0
        with patch("pcbknowledge.v2.routing.parse_board", side_effect=[before, after]), self.assertRaises(ValueError):
            unchanged_placement("a", "b")

    def test_native_pad_number_loss_is_not_accepted(self):
        before = {'nets': {}, 'outline': {}, 'footprints': {'H1': {'pads': {'1': []}}}}
        after = {'nets': {}, 'outline': {}, 'footprints': {'H1': {'pads': {'': []}}}}
        with patch('pcbknowledge.v2.routing.parse_board', side_effect=[before, after]), self.assertRaises(ValueError):
            unchanged_placement('a', 'b')
