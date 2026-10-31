"""Original synthetic manufacturing fixtures, with no external tool dependency."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from pcbknowledge.v2.fabrication import FUNCTIONS, check_positions, drill_count, export_outputs, profile_bounds, reread_outputs

PROFILE = '%FSLAX46Y46*%\n%MOMM*%\nX0Y0D02*\nX10000000Y0D01*\nX10000000Y-5000000D01*\n'
PROFILE += 'X0Y-5000000D01*\nX0Y0D01*\nM02*\n'
POSITIONS = 'Ref,Val,Package,PosX,PosY,Rot,Side\nR1,,chip,2,-3,90,top\n'
DRILLS = 'M48\n; decimal\nMETRIC\n%\nG90\nG05\nT1\nX2.0Y-3.0\nM30\n'


def board():
    return {'outline': {'bounds': [0, 0, 10, 5]}, 'vias': [], 'footprints': {
        'R1': {'at': [2, 3], 'rotation': 90, 'layer': 'F.Cu', 'pads': {'1': [{'drill': 1}]}}}}


class FabricationTests(unittest.TestCase):
    def test_profile_extents_and_curves_or_open_paths_rejected(self):
        self.assertEqual(profile_bounds(PROFILE), [0, 0, 10, 5])
        for text in (PROFILE.replace('X0Y0D01*', ''), PROFILE + 'G02*\n'):
            with self.assertRaises(ValueError):
                profile_bounds(text)

    def test_drills_and_slots_counted_once_and_routes_rejected(self):
        self.assertEqual(drill_count(DRILLS), 1)
        self.assertEqual(drill_count(DRILLS.replace('X2.0Y-3.0', 'X2.0Y-3.0G85X2.0Y-4.0')), 1)
        for text in (DRILLS.replace('METRIC', 'INCH'), DRILLS + 'G01X2Y3\n'):
            with self.assertRaises(ValueError):
                drill_count(text)

    def test_positions_require_exact_identity_side_rotation_and_finite_coordinates(self):
        self.assertEqual(check_positions(POSITIONS, board(), {'R1'}), 1)
        invalid = [POSITIONS.splitlines()[0] + '\n', POSITIONS + POSITIONS.splitlines()[1] + '\n',
                   POSITIONS.replace('R1', 'U9'), POSITIONS.replace('2,-3', 'nan,-3'),
                   POSITIONS.replace('90,top', '0,top'), POSITIONS.replace('top', 'bottom')]
        for text in invalid:
            with self.assertRaises(ValueError):
                check_positions(text, board(), {'R1'})

    def test_full_reread_checks_layers_extents_drills_and_smt_refs(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            for index, function in enumerate(sorted(FUNCTIONS)):
                content = PROFILE if function == 'Profile,NP' else 'M02*\n'
                (path / f'{index}.gm1').write_text('%TF.FileFunction,' + function + '*%\n' + content)
            (path / 'board.drl').write_text(DRILLS)
            (path / 'positions.csv').write_text(POSITIONS)
            intent = {'bom': [{'mount_type': 'SMT', 'refs': ['R1']}]}
            self.assertEqual(reread_outputs(path, board(), intent)['status'], 'PASS')
            (path / 'positions.csv').unlink()
            with self.assertRaises(ValueError):
                reread_outputs(path, board(), intent)
            (path / 'positions.csv').write_text(POSITIONS)
            (path / '0.gm1').unlink()
            with self.assertRaises(ValueError):
                reread_outputs(path, board(), intent)

    def test_missing_tool_and_stale_outputs_never_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / 'build/fab'
            result = export_outputs(root / 'build/a.kicad_pcb', target, {},
                                    {'kicad': {'status': 'NOT_FOUND'}}, root=root)
            self.assertEqual(result['status'], 'NOT_RUN')
            target.mkdir(parents=True)
            with self.assertRaises(ValueError):
                export_outputs(root / 'build/a.kicad_pcb', target, {}, {}, root=root)

    def test_export_does_not_filter_out_untagged_smt_and_reports_failed_reread(self):
        with tempfile.TemporaryDirectory() as folder, patch('pcbknowledge.v2.fabrication.run_process') as process:
            root = Path(folder)
            (root / 'build').mkdir()
            (root / 'build/a.kicad_pcb').write_text('(kicad_pcb)')
            process.return_value = {'status': 'PASS'}
            with patch('pcbknowledge.v2.fabrication.parse_board', return_value=board()):
                result = export_outputs(root / 'build/a.kicad_pcb', root / 'build/fab', {},
                                        {'kicad': {'status': 'FOUND', 'path': '/tool'}}, root=root)
            self.assertEqual(result['status'], 'FAIL')
            commands = [call.args[0] for call in process.call_args_list]
            self.assertNotIn('--smd-only', next(command for command in commands if 'pos' in command))
