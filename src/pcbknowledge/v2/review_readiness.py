"""Owner inspection eligibility, separate from strict A3-A5 acceptance."""
import hashlib
from pathlib import Path

from .svg_check import check_svg


def _verify_files(directory, hashes, required):
    if not isinstance(hashes, dict) or not required <= hashes.keys():
        return False
    for name, digest in hashes.items():
        relative = Path(name)
        path = directory / relative
        if relative.is_absolute() or '..' in relative.parts or not path.is_file():
            return False
        if any(part.is_symlink() for part in (path, *path.parents)):
            return False
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return False
    return True


def owner_review_ready(report):
    try:
        return _eligible(report)
    except (OSError, ValueError, TypeError, KeyError):
        return False


def _eligible(report):
    if report.get('placement', {}).get('status') != 'PASS':
        return False
    checks = report.get('layout', {}).get('checks', [])
    if not checks or any(row.get('result') not in ('PASS', 'NOT_CHECKABLE') for row in checks):
        return False
    if any(not isinstance(row.get('reason'), str) or not row['reason'].strip()
           for row in checks if row['result'] == 'NOT_CHECKABLE'):
        return False
    drc = report.get('drc', {})
    if (drc.get('a4') != 'PASS' or drc.get('drc_status') != 'PASS'
            or drc.get('status') not in ('PASS', 'NOT_CHECKABLE')
            or drc.get('exit_code') != 0 or drc.get('finding_count') != 0):
        return False
    if drc['status'] == 'NOT_CHECKABLE' and not any(row['result'] == 'NOT_CHECKABLE' for row in checks):
        return False
    native = drc.get('report', {})
    if any(native.get(key) != [] for key in ('violations', 'unconnected_items', 'schematic_parity')):
        return False
    fabrication = report.get('fabrication', {})
    if fabrication.get('status') != 'PASS' or fabrication.get('reread', {}).get('status') != 'PASS':
        return False
    if report.get('bringup', {}).get('range_coverage') != 'COMPLETE':
        return False
    board = Path(report.get('board', ''))
    if not board.is_file() or board.is_symlink() or drc.get('board') != str(board):
        return False
    required = {board.name, board.with_suffix('.kicad_pro').name, board.with_suffix('.kicad_dru').name}
    if not _verify_files(board.parent, drc.get('input_sha256'), required):
        return False
    digest = hashlib.sha256(board.read_bytes()).hexdigest()
    if drc.get('input_sha256', {}).get(board.name) != digest or fabrication.get('input_sha256') != digest:
        return False
    checklist = Path(report.get('bringup', {}).get('checklist', ''))
    if not checklist.is_file() or checklist.is_symlink() or not checklist.stat().st_size:
        return False
    output = Path(fabrication.get('output', ''))
    if not _verify_files(output, fabrication.get('artifact_sha256'), {'top.svg', 'bottom.svg'}):
        return False
    paths = [Path(value) for value in report.get('svg_paths', [])]
    if not {'top.svg', 'bottom.svg'} <= {path.name for path in paths}:
        return False
    if set(paths) != {output / 'top.svg', output / 'bottom.svg'}:
        return False
    for path in paths:
        check_svg(path.read_text(encoding='utf-8'))
    return True
