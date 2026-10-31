"""Native manufacturing exports with independent standard-library output checks."""
from __future__ import annotations

import csv
import io
import hashlib
import math
from pathlib import Path
import re

from pcbknowledge.v2.boardview import parse_board
from .layout_tools import derived_path, run_process
from .svg_check import check_svg

LAYERS = ('F.Cu', 'B.Cu', 'F.Mask', 'B.Mask', 'F.Paste', 'B.Paste',
          'F.Silkscreen', 'B.Silkscreen', 'Edge.Cuts')
FUNCTIONS = {'Copper,L1,Top', 'Copper,L2,Bot', 'Soldermask,Top', 'Soldermask,Bot',
             'Paste,Top', 'Paste,Bot', 'Legend,Top', 'Legend,Bot', 'Profile,NP'}


class UnsupportedFabrication(ValueError):
    """The exported syntax exceeds the independent reader's supported proof."""


def read_text(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('Missing, unsafe or oversized fabrication output')
    return path.read_text(encoding='utf-8')


def profile_bounds(text):
    """Read a closed linear profile in KiCad absolute metric Gerber form."""
    match = re.search(r'%FSLAX(\d)(\d)Y\1\2\*%', text)
    if not match or '%MOMM*%' not in text:
        raise UnsupportedFabrication('Unsupported Gerber coordinate format')
    if re.search(r'G0?[23]\*|G3[67]\*|%[LM][MR]', text):
        raise UnsupportedFabrication('Unsupported curved, region or transformed profile')
    scale = 10 ** int(match.group(2))
    paths, current = [], []
    for line in text.splitlines():
        if not line.startswith(('X', 'Y')):
            continue
        row = re.fullmatch(r'X(-?\d+)Y(-?\d+)D0([12])\*', line)
        if row is None:
            raise UnsupportedFabrication('Unsupported profile operation')
        point = (int(row[1]) / scale, -int(row[2]) / scale)
        if row[3] == '2':
            if current:
                paths.append(current)
            current = [point]
        else:
            if not current:
                raise ValueError('Profile draw without start')
            current.append(point)
    if current:
        paths.append(current)
    if len(paths) != 1 or len(paths[0]) < 5 or paths[0][0] != paths[0][-1]:
        raise ValueError('Exactly one closed linear board profile required')
    points = paths[0]
    return [min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points)]


def drill_count(text):
    if 'METRIC' not in text or 'decimal' not in text or 'G90' not in text or 'M30' not in text:
        raise UnsupportedFabrication('Unsupported drill units, coordinates or termination')
    count = 0
    for line in text.splitlines():
        if not line or line.startswith(';'):
            continue
        if line.startswith(('X', 'Y')):
            number = r'-?\d+(?:\.\d+)?'
            point = 'X' + number + 'Y' + number
            if not re.fullmatch(point + '(?:G85' + point + ')?', line):
                raise UnsupportedFabrication('Unsupported drill hit or slot')
            count += 1
        elif line.startswith(('G00', 'G01', 'G02', 'G03', 'M15', 'R')):
            raise UnsupportedFabrication('Unsupported routed or repeated drill geometry')
    return count


def check_positions(text, board, smt_refs, *, bom_refs=None):
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != ['Ref', 'Val', 'Package', 'PosX', 'PosY', 'Rot', 'Side']:
        raise UnsupportedFabrication('Unsupported position CSV header')
    rows = {}
    for row in reader:
        ref = row['Ref']
        if ref in rows or ref not in board['footprints']:
            raise ValueError('Duplicate or unknown position reference')
        actual = [float(row[key]) for key in ('PosX', 'PosY', 'Rot')]
        if not all(math.isfinite(value) for value in actual):
            raise ValueError('Nonfinite position coordinate')
        fp = board['footprints'][ref]
        expected = [fp['at'][0], -fp['at'][1], fp['rotation'] % 360]
        delta = abs((actual[2] - expected[2] + 180) % 360 - 180)
        side = {'F.Cu': 'top', 'B.Cu': 'bottom'}.get(fp['layer'])
        if any(abs(a - b) > 1e-5 for a, b in zip(actual[:2], expected[:2])) or delta > 1e-5:
            raise ValueError('Position or rotation differs from board: ' + ref)
        if row['Side'] != side:
            raise ValueError('Position side differs from board: ' + ref)
        rows[ref] = row
    if set(smt_refs) - rows.keys():
        raise ValueError('SMT BOM references missing positions: ' + ', '.join(sorted(set(smt_refs) - rows.keys())))
    if bom_refs is not None and set(rows) != set(bom_refs):
        raise ValueError('Position references differ from complete BOM')
    return len(rows)


def reread_outputs(directory, board, intent):
    directory = Path(directory)
    functions = {}
    for path in directory.iterdir():
        if path.suffix not in ('.gtl', '.gbl', '.gts', '.gbs', '.gtp', '.gbp', '.gto', '.gbo', '.gm1'):
            continue
        text = read_text(path)
        match = re.search(r'%TF.FileFunction,([^*]+)\*%', text)
        if not match or match[1] in functions or 'M02*' not in text:
            raise ValueError('Missing or duplicate Gerber layer identity or termination')
        functions[match[1]] = text
    if set(functions) != FUNCTIONS:
        raise ValueError('Gerber layer set differs from required two-layer fabrication stack')
    bounds = profile_bounds(functions['Profile,NP'])
    if any(abs(a - b) > 1e-5 for a, b in zip(bounds, board['outline']['bounds'])):
        raise ValueError('Fabrication outline extents differ from board')
    files = sorted(directory.glob('*.drl'))
    if not files:
        raise ValueError('Drill output is missing')
    drills = sum(drill_count(read_text(path)) for path in files)
    expected = len(board['vias']) + sum(bool(pad['drill']) for fp in board['footprints'].values()
                                       for pads in fp['pads'].values() for pad in pads)
    if drills != expected:
        raise ValueError('Fabrication drill/slot count differs from board')
    smt = {ref for row in intent['bom'] if row['mount_type'] == 'SMT' for ref in row['refs']}
    bom_refs = [ref for row in intent['bom'] for ref in row['refs']]
    if len(bom_refs) != len(set(bom_refs)) or set(bom_refs) != set(board['footprints']):
        raise ValueError('Complete BOM and board references differ or repeat')
    positions = check_positions(read_text(directory / 'positions.csv'), board, smt, bom_refs=bom_refs)
    renders = {side: check_svg(read_text(directory / (side + '.svg'))) for side in ('top', 'bottom')}
    return {'status': 'PASS', 'layers': sorted(functions), 'bounds_mm': bounds,
            'drill_slot_count': drills, 'position_count': positions, 'smt_reference_count': len(smt),
            'renders': renders}


def export_outputs(board_path, output, intent, tools, *, root):
    board_path, output = derived_path(root, board_path), derived_path(root, output)
    if output.exists():
        raise ValueError('Fabrication output directory must be fresh')
    tool = tools['kicad']
    if tool['status'] != 'FOUND':
        return {'status': 'NOT_RUN' if tool['status'] == 'NOT_FOUND' else 'FAIL', 'reason': 'KiCad unavailable'}
    fingerprint = hashlib.sha256(board_path.read_bytes()).hexdigest()
    output.mkdir(parents=True)
    jobs = [('gerbers', ['gerbers', '--layers', ','.join(LAYERS), '-o', str(output)]),
            ('drill', ['drill', '--format', 'excellon', '--excellon-units', 'mm',
                       '--excellon-zeros-format', 'decimal', '--excellon-oval-format', 'alternate',
                       '-o', str(output)]),
            ('positions', ['pos', '--format', 'csv', '--units', 'mm', '-o', str(output / 'positions.csv')]),
            ('top-svg', ['svg', '--mode-single', '--fit-page-to-board', '--layers',
                         'F.Cu,F.Silkscreen,F.Fab,Edge.Cuts', '-o', str(output / 'top.svg')]),
            ('bottom-svg', ['svg', '--mode-single', '--mirror', '--fit-page-to-board', '--layers',
                            'B.Cu,B.Silkscreen,B.Fab,Edge.Cuts', '-o', str(output / 'bottom.svg')])]
    results = {}
    for name, arguments in jobs:
        results[name] = run_process([tool['path'], 'pcb', 'export', *arguments, str(board_path)],
                                    root=root, directory=output / ('process-' + name))
        if results[name]['status'] != 'PASS':
            return {'status': 'FAIL', 'processes': results, 'reread': {'status': 'NOT_RUN'}}
    try:
        reread = reread_outputs(output, parse_board(board_path), intent)
    except UnsupportedFabrication as error:
        reread = {'status': 'NOT_CHECKABLE', 'reason': str(error)}
    except (OSError, ValueError, KeyError, TypeError) as error:
        reread = {'status': 'FAIL', 'reason': str(error)}
    if hashlib.sha256(board_path.read_bytes()).hexdigest() != fingerprint:
        reread = {'status': 'FAIL', 'reason': 'Export modified source board'}
    return {'status': reread['status'], 'processes': results, 'reread': reread, 'input_sha256': fingerprint}
