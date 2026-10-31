"""Native DSN/session/fill sequence with unmodified placement and source inputs."""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil

from pcbknowledge.v2.boardview import parse_board
from pcbknowledge.v2.handoff_rules import net_widths
from .layout_tools import derived_path, run_bridge, run_router
from .specctra import configure_dsn, validate_session, verify_native_vias
from .routing_planes import project_routing_planes


def input_fingerprints(board):
    paths = [board, board.with_suffix('.kicad_pro'), board.with_suffix('.kicad_dru')]
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise ValueError('Board, project and rules must be regular files')
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def copy_rules(source, target, root):
    for suffix in ('.kicad_pro', '.kicad_dru'):
        old, new = derived_path(root, source.with_suffix(suffix)), derived_path(root, target.with_suffix(suffix))
        if not old.is_file() or new.exists():
            raise ValueError('Project/rules need present source and fresh destination')
        shutil.copyfile(old, new)


def _canonical_geometry(value, key=None):
    # Native KiCad stores nanometer coordinates and may reorder layer membership.
    if key == "rotation" and isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(value % 360, 6)
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, list):
        values = [_canonical_geometry(item) for item in value]
        return sorted(values) if key == 'layers' else values
    if isinstance(value, dict):
        return {name: _canonical_geometry(item, name) for name, item in value.items()}
    return value


def unchanged_placement(source, final):
    before, after = parse_board(source), parse_board(final)
    if before['nets'] != after['nets'] or before['outline'] != after['outline']:
        raise ValueError('Native merge changed net definitions or outline')
    if _canonical_geometry(before['footprints']) != _canonical_geometry(after['footprints']):
        raise ValueError('Native merge changed component placement, pad identities or geometry')
    return {'status': 'PASS', 'component_count': len(after['footprints'])}


def _route(board, directory, intent, catalog, tools, root, result):
    dsn = directory / 'routing.dsn'
    result['export_dsn'] = run_bridge('export-dsn', board, dsn, tools, root=root,
                                      directory=directory / 'process-dsn')
    if result['export_dsn']['status'] != 'PASS':
        return result['export_dsn']['status']
    verify_native_vias(dsn.read_text(), catalog.get(intent['fab_profile'], 'fab_profile'))
    projected, result['dsn_projection'] = project_routing_planes(dsn.read_text(), parse_board(board))
    dsn.write_text(configure_dsn(projected, intent, catalog), encoding='utf-8')
    session = directory / 'routing.ses'
    result['router'] = run_router(dsn, session, tools, root=root, directory=directory / 'process-router')
    if result['router']['status'] != 'PASS':
        return result['router']['status']
    widths = net_widths(intent, catalog.get(intent['fab_profile'], 'fab_profile'))
    result['session'] = validate_session(session.read_text(), dsn.read_text(), widths, dsn_name=dsn.name)
    merged = directory / 'merged.kicad_pcb'
    result['merge'] = run_bridge('merge-session', board, merged, tools, root=root,
                                 directory=directory / 'process-merge', session=session)
    if result['merge']['status'] != 'PASS':
        return result['merge']['status']
    copy_rules(board, merged, root)
    filled = directory / 'routed.kicad_pcb'
    result['fill'] = run_bridge('fill', merged, filled, tools, root=root, directory=directory / 'process-fill')
    if result['fill']['status'] != 'PASS':
        return result['fill']['status']
    copy_rules(merged, filled, root)
    result['preservation'] = unchanged_placement(board, filled)
    result['board'] = str(filled)
    return 'PASS'


def route_board(board, directory, intent, catalog, tools, *, root):
    board, directory = derived_path(root, board), derived_path(root, directory)
    if directory.exists():
        raise ValueError('Routing output directory must be fresh')
    for suffix in ('.kicad_pro', '.kicad_dru'):
        derived_path(root, board.with_suffix(suffix))
    fingerprints = input_fingerprints(board)
    directory.mkdir(parents=True)
    result = {'status': 'FAIL', 'input_sha256': fingerprints, 'routing_completeness': 'NOT_CHECKABLE'}
    try:
        result['status'] = _route(board, directory, intent, catalog, tools, root, result)
    except (OSError, ValueError, TypeError, KeyError) as error:
        result.update(status='FAIL', reason=str(error))
    if input_fingerprints(board) != fingerprints:
        result.update(status='FAIL', reason='Routing modified original board/project/rules')
    return result
