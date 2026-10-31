"""One explicit, authenticated failed-pad reservation and strict final routing check."""
import hashlib
import json
from pathlib import Path
import pcbknowledge
from .bundle import Bundle
from .expansion import validate_expansion
from .layout_tools import derived_path, run_process
from .routing import input_fingerprints, copy_rules, route_board
from .fanout_repair import _copy_library
from .layout import check_board
from .drc import run_drc
from .reservation_policy import classify_reservation


def _write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def _authenticate(root, paths):
    paths = {name: derived_path(root, path) for name, path in paths.items()}
    if paths['output'].exists():
        raise ValueError('Reservation output must be fresh')
    graph = derived_path(root, paths['original'].parent / 'graph.json')
    intent = json.loads(paths['intent'].read_text())
    bundle = Bundle(paths['bundle'])
    validate_expansion(bundle, intent, json.loads(graph.read_text()))
    files = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
             for name, p in paths.items() if name != 'output'}
    files[str(graph)] = hashlib.sha256(graph.read_bytes()).hexdigest()
    for name in ('original', 'current', 'prior'):
        files.update(input_fingerprints(paths[name]))
    return paths, intent, bundle, files


def _prepare(root, paths, pad_uuid, tools, result):
    directory = paths['output']
    bootstrap = '\n'.join([
        'import runpy', 'import sys', 'sys.path.insert(0, sys.argv.pop(1))',
        'sys.argv[0] = "pcbknowledge.v2.reservation_prepare"',
        'runpy.run_module("pcbknowledge.v2.reservation_prepare", run_name="__main__")'])
    args = [tools['kicad_python']['path'], '-c', bootstrap,
            str(Path(pcbknowledge.__file__).resolve().parents[1]), str(root)]
    args.extend(str(paths[name]) for name in ('original', 'current', 'prior', 'drc', 'intent', 'bundle'))
    args.extend([pad_uuid, str(directory / 'seed')])
    result['native_prepare'] = run_process(args, root=root, directory=directory / 'native-prepare', timeout=120)
    if result['native_prepare']['status'] != 'PASS':
        return None
    seed = directory / 'seed' / 'seed.kicad_pcb'
    receipt = json.loads((seed.parent / 'seed-receipt.json').read_text())
    copy_rules(paths['original'], seed, root)
    _copy_library(paths['original'], seed)
    drc = run_drc(seed, seed.parent / 'drc.json', root=root, kicad=tools['kicad']['path'])
    result['seed_policy'] = classify_reservation(
        drc, receipt, paths['current'].read_text(), paths['drc'].read_text())
    _write(seed.parent / 'routing-permission.json', result['seed_policy'])
    return (seed, receipt) if result['seed_policy']['routing_allowed'] else None


def _route_and_check(root, paths, prepared, intent, bundle, tools, result):
    seed, receipt = prepared
    directory = paths['output']
    result['route'] = route_board(seed, directory / 'routing', intent, bundle.catalog,
                                  tools, root=root, seed_receipt=receipt,
                                  scope={'current': paths['current'], 'baseline': paths['drc']})
    _write(directory / 'route-report.json', result['route'])
    if result['route']['status'] != 'PASS':
        return
    final = Path(result['route']['board'])
    _copy_library(paths['original'], final)
    result['layout'] = check_board(final, intent, bundle.catalog)
    _write(directory / 'layout.json', result['layout'])
    result['drc'] = run_drc(final, directory / 'drc.json', root=root,
                            layout_report=result['layout'], kicad=tools['kicad']['path'])
    result['board'] = str(final)
    from .reservation_protection import verify_seed_retention
    from .routing_scope import verify_scope_retention
    result['seed_retention'] = verify_seed_retention(seed.read_text(), final.read_text(), receipt)
    result['scope_retention'] = verify_scope_retention(
        seed.read_text(), final.read_text(), receipt, result['route']['routing_scope'])
    if result['layout']['result'] == 'PASS' and result['drc']['a4'] == 'PASS':
        result['status'] = 'PASS'


def reserve_route(original, current, prior, drc, intent, bundle, failed_pad_uuid, tools, output, *, root):
    """Single bounded attempt; output retains every native finding and exact seed receipt."""
    if not isinstance(failed_pad_uuid, str) or not failed_pad_uuid.strip():
        raise ValueError('Explicit failed-pad UUID is required')
    root = Path(root).resolve()
    paths, intent, bundle, files = _authenticate(root, dict(
        original=original, current=current, prior=prior, drc=drc, intent=intent, bundle=bundle, output=output))
    result = {'status': 'FAIL', 'authority_sha256': files, 'failed_pad_uuid': failed_pad_uuid}
    for name in ('kicad', 'kicad_python', 'java', 'freerouting'):
        if not tools.get(name, {}).get('path'):
            return dict(result, status='NOT_RUN', reason='Required tool unavailable: ' + name)
    paths['output'].mkdir()
    try:
        prepared = _prepare(root, paths, failed_pad_uuid, tools, result)
        if prepared:
            _route_and_check(root, paths, prepared, intent, bundle, tools, result)
    except (OSError, ValueError, KeyError, TypeError) as error:
        result.update(status='FAIL', reason=str(error))
    result['router_seconds'] = result.get('route', {}).get('router', {}).get('runtime_seconds', 0)
    if any(not Path(path).is_file() or hashlib.sha256(Path(path).read_bytes()).hexdigest() != sha
           for path, sha in files.items()):
        result.update(status='FAIL', reason='Reservation changed source authority')
    _write(paths['output'] / 'report.json', result)
    return result
