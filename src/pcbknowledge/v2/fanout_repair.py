"""Bounded repair orchestration; native geometry stays in an explicit subprocess."""
import hashlib
import json
import math
from pathlib import Path
import pcbknowledge

from pcbknowledge.v2.bundle import Bundle
from pcbknowledge.v2.drc import run_drc
from pcbknowledge.v2.layout import check_board
from pcbknowledge.v2.layout_tools import derived_path, run_process
from pcbknowledge.v2.routing import copy_rules, input_fingerprints, route_board
from .fanout_requests import extract_requests
from .fanout_seed_policy import classify_seed


def _write(path, document):
    path.write_text(json.dumps(document, indent=2) + '\n')


def _copy_library(source, target):
    # Reuse the existing DRC library validator before copying a generated library.
    from pcbknowledge.v2.drc import _library_inputs
    _library_inputs(source)
    from .layout_pipeline import _copy_library as copy_generated_library
    copy_generated_library(source.parent, target.parent)


def _attempt(root, original, directory, history, intent_path, bundle_path, tools, intent, catalog, result=None):
    directory.mkdir()
    _write(directory / 'history.json', history)
    seed_dir = directory / 'seed'
    bootstrap = '\n'.join([
        'import runpy', 'import sys', 'sys.path.insert(0, sys.argv.pop(1))',
        'sys.argv[0] = "pcbknowledge.v2.fanout_prepare"',
        'runpy.run_module("pcbknowledge.v2.fanout_prepare", run_name="__main__")'])
    argv = [tools['kicad_python']['path'], '-c', bootstrap,
            str(Path(pcbknowledge.__file__).resolve().parents[1]), str(root), str(original),
            str(directory / 'history.json'), str(intent_path), str(bundle_path), str(seed_dir)]
    result = result if result is not None else {}
    result.update(status='FAIL', native_prepare=run_process(
        argv, root=root, directory=directory / 'native-prepare', timeout=120))
    if result['native_prepare']['status'] != 'PASS':
        return result
    seed = seed_dir / 'seed.kicad_pcb'
    receipt = json.loads((seed_dir / 'seed-receipt.json').read_text())
    copy_rules(original, seed, root)
    _copy_library(original, seed)
    drc = run_drc(seed, seed_dir / 'drc.json', root=root, kicad=tools['kicad']['path'])
    result['seed_policy'] = classify_seed(drc, receipt)
    _write(seed_dir / 'routing-permission.json', result['seed_policy'])
    if not result['seed_policy']['routing_allowed']:
        return result
    route = route_board(seed, directory / 'routing', intent, catalog, tools, root=root)
    result['route'] = route
    _write(directory / 'route-report.json', route)
    if route['status'] != 'PASS':
        return result
    final = Path(route['board'])
    _copy_library(original, final)
    layout = check_board(final, intent, catalog)
    _write(directory / 'layout.json', layout)
    drc = run_drc(final, directory / 'drc.json', root=root, layout_report=layout, kicad=tools['kicad']['path'])
    result.update(board=str(final), drc_path=str(directory / 'drc.json'), layout=layout, drc=drc)
    result['status'] = 'PASS' if layout['result'] == 'PASS' and drc['a4'] == 'PASS' else 'FAIL'
    return result


def repair_routes(original, initial_board, initial_drc, intent_path, bundle_path, tools, output,
                  *, root, max_repairs, initial_router_seconds):
    """Attempt at most max_repairs; preserve every earlier board and native report.

    Fabrication is intentionally outside this helper and must consume final strict checks.
    """
    if type(max_repairs) is not int or not 0 <= max_repairs <= 8:
        raise ValueError('Repair budget must be explicit and between zero and eight')
    if (isinstance(initial_router_seconds, bool) or not isinstance(initial_router_seconds, (int, float))
            or not math.isfinite(initial_router_seconds) or initial_router_seconds < 0):
        raise ValueError('Initial measured router runtime is required')
    root = Path(root).resolve()
    original, board, drc_path, intent_path, bundle_path, output = [derived_path(root, p) for p in
        (original, initial_board, initial_drc, intent_path, bundle_path, output)]
    if output.exists():
        raise ValueError('Repair output must be fresh')
    fingerprints = input_fingerprints(original)
    intent = json.loads(intent_path.read_text())
    bundle = Bundle(bundle_path)
    from .expansion import validate_expansion
    graph_path = derived_path(root, original.parent / 'graph.json')
    validate_expansion(bundle, intent, json.loads(graph_path.read_text()))
    authority_files = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (graph_path, intent_path, bundle_path)}
    output.mkdir()
    history, attempts, seen_endpoints = [], [], set()
    report = {'status': 'FAIL', 'max_repairs': max_repairs, 'attempts': attempts,
              'router_seconds_total': initial_router_seconds, 'source_sha256': fingerprints,
              'authority_sha256': authority_files}
    for index in range(max_repairs):
        drc = json.loads(drc_path.read_text())
        native = drc.get('report', {})
        if native.get('violations') or native.get('schematic_parity') or not native.get('unconnected_items'):
            report['reason'] = 'No supported connectivity-only failure to repair'
            break
        selection = extract_requests(board.read_text(), drc)
        if not selection['requests']:
            report['reason'] = 'No failed SMT pad endpoints supported for fanout'
            break
        identities = {tuple(value) for value in selection['physical_ids'].values()}
        if identities <= seen_endpoints:
            report['reason'] = 'No new supported physical endpoint; prior candidates already attempted'
            break
        seen_endpoints.update(identities)
        history.append({'board': str(board), 'board_sha256': hashlib.sha256(board.read_bytes()).hexdigest(),
                        'drc': str(drc_path), 'drc_sha256': hashlib.sha256(drc_path.read_bytes()).hexdigest(),
                        'requests': selection['requests']})
        directory = output / ('attempt-' + str(index + 1))
        attempt = {'status': 'FAIL'}
        try:
            attempt = _attempt(root, original, directory, history, intent_path, bundle_path,
                               tools, intent, bundle.catalog, attempt)
        except (OSError, ValueError, KeyError, TypeError) as error:
            attempt.update(status='FAIL', reason=str(error))
        attempt['selection'] = selection
        attempts.append(attempt)
        if directory.is_dir():
            _write(directory / 'report.json', attempt)
        report['router_seconds_total'] += attempt.get('route', {}).get('router', {}).get('runtime_seconds', 0)
        if input_fingerprints(original) != fingerprints:
            report['reason'] = 'Repair modified original source board/project/rules'
            break
        if 'board' not in attempt:
            report['reason'] = 'Repair preparation or routing failed'
            break
        board, drc_path = Path(attempt['board']), Path(attempt['drc_path'])
        report.update(board=str(board), drc_path=str(drc_path))
        if attempt['status'] == 'PASS':
            report['status'] = 'PASS'
            break
    else:
        report['reason'] = 'Explicit repair budget exhausted'
    if input_fingerprints(original) != fingerprints or any(
            hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest
            for path, digest in authority_files.items()):
        report.update(status='FAIL', reason='Source or intent/bundle/graph authority changed during repair')
    _write(output / 'report.json', report)
    return report
