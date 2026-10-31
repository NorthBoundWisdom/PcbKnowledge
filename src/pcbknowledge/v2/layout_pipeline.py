"""Reference layout orchestration over authenticated intent, only below build/."""
from collections import Counter
from pathlib import Path
import shutil
import time

from pcbknowledge.serialization import canonical_json
from .boardview import parse_board
from .bringup import make_bringup, render_bringup
from .drc import run_drc
from .expansion import validate_expansion
from .fabrication import export_outputs
from .handoff import _syntax, export_handoff
from .layout import check_board
from .layout_tools import derived_path
from .placement import PlacementError, apply_positions, place_components
from .placement_search import BEAM_WIDTH, COMPATIBILITY_WORK_PER_BRANCH, MAX_COMPATIBILITY_WORK, MAX_DOMAIN_CANDIDATES
from .routing import route_board
from .sexpr import dumps, parse


def _copy_library(source, destination):
    shutil.copyfile(source / 'fp-lib-table', destination / 'fp-lib-table')
    shutil.copytree(source / 'pcbknowledge.pretty', destination / 'pcbknowledge.pretty')


def _counts(layout, drc):
    counts = Counter(row['result'] for row in layout.get('checks', []))
    native = drc.get('report', {})
    return {'layout': {name: counts[name] for name in ('PASS', 'FAIL', 'NOT_CHECKABLE')},
            'drc': {name: len(native[name]) if name in native else None
                    for name in ('violations', 'unconnected_items', 'schematic_parity')}}


def _route_and_check(board, output, intent, bundle, tools, root, report):
    unavailable = {name: tool['status'] for name, tool in tools.items() if tool['status'] != 'FOUND'}
    if unavailable:
        status = 'FAIL' if any(value != 'NOT_FOUND' for value in unavailable.values()) else 'NOT_RUN'
        report['router'] = {'status': status, 'runtime_seconds': 0, 'unavailable': unavailable}
        return board
    route = route_board(board, output / 'routing', intent, bundle.catalog, tools, root=root)
    report['routing'] = route
    report['router'] = route.get('router', {'status': 'NOT_RUN', 'runtime_seconds': 0,
                                           'reason': route.get('reason', 'Routing prerequisite failed')})
    if route['status'] != 'PASS':
        report['router'] = dict(report['router'], process_status=report['router']['status'],
                                status=route['status'], reason=route.get('reason', 'Routing postflight failed'))
        return board
    final = Path(route['board'])
    _copy_library(board.parent, final.parent)
    layout = check_board(final, intent, bundle.catalog)
    drc = run_drc(final, output / 'drc.json', root=root, layout_report=layout, kicad=tools['kicad']['path'])
    report.update(layout=layout, drc=drc)
    report['a3'] = 'PASS' if layout['result'] == 'PASS' else 'FAIL'
    report['a4'] = drc['a4']
    fabrication = export_outputs(final, output / 'fabrication', intent, tools, root=root)
    report['fabrication'] = fabrication
    if (output / 'fabrication').is_dir():
        shutil.copyfile(board.parent / 'assembly.csv', output / 'fabrication/assembly.csv')
    report['a5'] = ('PASS' if report['a3'] == report['a4'] == fabrication['status'] == 'PASS' else 'FAIL')
    return final


def run_layout(intent, bundle, graph, output, tools, *, root, grid_mm=.5, max_states=200000):
    output = derived_path(root, output)
    if output.exists():
        raise ValueError('Reference layout requires a fresh output directory')
    validate_expansion(bundle, intent, graph)
    report = {'schema': 'pcbknowledge.reference-layout.v1', 'brief': intent['brief_id'],
              'bundle_commit': bundle.commit, 'block_graph_sha256': intent['block_graph_sha256'],
              'tools': tools, 'search': {'grid_mm': grid_mm, 'max_states': max_states,
                                        'max_domain_candidates': MAX_DOMAIN_CANDIDATES, 'beam_width': BEAM_WIDTH,
                                        'max_compatibility_work': min(MAX_COMPATIBILITY_WORK,
                                                                      max_states * COMPATIBILITY_WORK_PER_BRANCH)},
              'a3': 'NOT_RUN', 'a4': 'NOT_RUN', 'a5': 'NOT_RUN',
              'placement': {'status': 'NOT_RUN'}, 'router': {'status': 'NOT_RUN', 'runtime_seconds': 0}}
    handoff = export_handoff(intent, bundle, graph, output / 'handoff')
    board = handoff / 'design.kicad_pcb'
    placement_started = time.monotonic()
    try:
        positions = place_components(intent, bundle.catalog, grid_mm=grid_mm, max_states=max_states)
        tree = apply_positions(parse(board.read_text()), positions)
        from .layout_copper import add_copper
        tree = add_copper(tree, intent, bundle.catalog)
        board.write_text(dumps(_syntax(tree)), encoding='utf-8', newline='\n')
        report['placement'] = {'status': 'PASS', 'positions': positions, 'grid_mm': grid_mm,
                               'runtime_seconds': round(time.monotonic() - placement_started, 6)}
        board = _route_and_check(board, output, intent, bundle, tools, root, report)
    except PlacementError as error:
        report.update(a3='FAIL', placement={'status': 'FAIL', 'reason': error.reason,
                                          'constraint_indexes': list(error.constraints), 'search_states': error.states,
                                          'runtime_seconds': round(time.monotonic() - placement_started, 6)})
    except (OSError, ValueError, KeyError, TypeError) as error:
        report.update(a3='FAIL', reason=str(error))
    if 'layout' not in report:
        report['layout'] = check_board(board, intent, bundle.catalog)
    bringup = make_bringup(intent, graph, bundle.briefs[graph['brief']], bundle.catalog,
                           board=parse_board(board))
    (output / 'bringup.json').write_text(canonical_json(bringup), encoding='utf-8', newline='\n')
    (output / 'bringup.md').write_text(render_bringup(bringup), encoding='utf-8', newline='\n')
    report['bringup'] = {'range_coverage': bringup['range_coverage'],
                         'unresolved_rail_ranges': bringup['unresolved_rail_ranges'],
                         'checklist': str(output / 'bringup.md')}
    report['counts'] = _counts(report['layout'], report.get('drc', {}))
    report['not_checkable'] = [row for row in report['layout']['checks'] if row['result'] == 'NOT_CHECKABLE']
    report['board'] = str(board)
    ready = all(report[key] == 'PASS' for key in ('a3', 'a4', 'a5')) and bringup['range_coverage'] == 'COMPLETE'
    report['review_ready'] = ready
    report['status'] = 'PASS' if ready else 'FAIL'
    report['svg_paths'] = [str(path) for path in sorted((output / 'fabrication').rglob('*.svg'))]
    (output / 'report.json').write_text(canonical_json(report), encoding='utf-8', newline='\n')
    return report
