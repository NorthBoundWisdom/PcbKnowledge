"""Manual inspection eligibility never changes strict acceptance levels."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest

from pcbknowledge.v2.review_readiness import owner_review_ready


def fixture(root):
    for name in ('board.kicad_pcb', 'board.kicad_pro', 'board.kicad_dru', 'top.svg', 'bottom.svg', 'bringup.md'):
        (root / name).write_text(name)
    for name in ('top.svg', 'bottom.svg'):
        (root / name).write_text('<svg viewBox="0 0 10 10"><path d="M0 0 L5 5"/></svg>')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
    board = root / 'board.kicad_pcb'
    digest = hashlib.sha256(board.read_bytes()).hexdigest()
    return {'placement': {'status': 'PASS'}, 'layout': {'checks': [
        {'result': 'PASS'}, {'result': 'NOT_CHECKABLE', 'reason': 'Kelvin branch proof unavailable'}]},
        'drc': {'status': 'PASS', 'a4': 'PASS', 'board': str(board), 'input_sha256': {name: value for name, value in hashes.items() if name.startswith('board.')},
                'report': {'violations': [], 'unconnected_items': [], 'schematic_parity': []}},
        'fabrication': {'status': 'PASS', 'reread': {'status': 'PASS'}, 'input_sha256': digest,
                        'output': str(root), 'artifact_sha256': {name: hashes[name] for name in ('top.svg', 'bottom.svg')}},
        'bringup': {'range_coverage': 'COMPLETE', 'checklist': str(root / 'bringup.md')},
        'svg_paths': [str(root / 'top.svg'), str(root / 'bottom.svg')], 'board': str(board),
        'a3': 'FAIL', 'a4': 'PASS', 'a5': 'FAIL', 'status': 'FAIL'}


class ReviewReadinessTests(unittest.TestCase):
    def test_named_unknowns_allow_inspection_without_changing_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            report = fixture(Path(directory))
            before = deepcopy(report)
            self.assertTrue(owner_review_ready(report))
            self.assertEqual(report, before)
            self.assertEqual(report['a5'], 'FAIL')

    def test_every_native_finding_and_missing_count_blocks_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            report = fixture(Path(directory))
            for key in ('violations', 'unconnected_items', 'schematic_parity'):
                for value in ([{'type': 'finding'}], None):
                    changed = deepcopy(report)
                    changed['drc']['report'][key] = value
                    self.assertFalse(owner_review_ready(changed))

    def test_layout_failure_or_unexplained_unknown_blocks_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            report = fixture(Path(directory))
            for row in ({'result': 'FAIL'}, {'result': 'NOT_CHECKABLE'},
                        {'result': 'NOT_CHECKABLE', 'reason': '  '}, {'result': 'OTHER'}):
                changed = deepcopy(report)
                changed['layout']['checks'].append(row)
                self.assertFalse(owner_review_ready(changed))

    def test_missing_artifact_changed_board_or_unchecked_fabrication_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = fixture(root)
            for name in ('top.svg', 'bottom.svg', 'bringup.md', 'board.kicad_pcb'):
                path = root / name
                original = path.read_bytes()
                path.unlink()
                self.assertFalse(owner_review_ready(report))
                path.write_bytes(original)
            for field in ('status', 'reread'):
                changed = deepcopy(report)
                changed['fabrication'][field] = 'FAIL' if field == 'status' else {'status': 'NOT_RUN'}
                self.assertFalse(owner_review_ready(changed))
            (root / 'board.kicad_pcb').write_text('changed')
            self.assertFalse(owner_review_ready(report))

    def test_incomplete_ranges_placement_and_input_bindings_block_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            report = fixture(Path(directory))
            cases = [('bringup', 'range_coverage', 'UNKNOWN'), ('placement', 'status', 'FAIL'),
                     ('drc', 'a4', 'FAIL'), ('drc', 'status', 'NOT_RUN'),
                     ('drc', 'input_sha256', {}), ('fabrication', 'input_sha256', 'wrong')]
            for section, key, value in cases:
                changed = deepcopy(report)
                changed[section][key] = value
                self.assertFalse(owner_review_ready(changed))

    def test_changed_native_settings_and_stale_or_non_svg_render_block(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = fixture(root)
            for name in ('board.kicad_pro', 'board.kicad_dru', 'top.svg', 'bottom.svg'):
                path = root / name
                original = path.read_bytes()
                path.write_text('replacement')
                self.assertFalse(owner_review_ready(report))
                path.write_bytes(original)
            path = root / 'top.svg'
            path.write_text('not an SVG')
            report['fabrication']['artifact_sha256']['top.svg'] = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertFalse(owner_review_ready(report))
