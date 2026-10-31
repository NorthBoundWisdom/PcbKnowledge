"""External native one-pad reservation proposal and exact derived-copper emission."""
import argparse
import hashlib
import json
from pathlib import Path
from .bundle import Bundle
from .expansion import validate_expansion
from .kicad_bridge import _path
from .routing import input_fingerprints, unchanged_placement
from .reservation_core import compose, digest
from .reservation_native import reservation


def _inputs(root, names):
    paths = {name: _path(root, path, exists=True) for name, path in names.items()}
    graph = _path(root, paths['original'].parent / 'graph.json', exists=True)
    authority = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [*paths.values(), graph]}
    intent = json.loads(paths['intent'].read_text())
    bundle = Bundle(paths['bundle'])
    validate_expansion(bundle, intent, json.loads(graph.read_text()))
    report = json.loads(paths['drc'].read_text())
    native = report['report']
    count = sum(len(native[key]) for key in ('violations', 'unconnected_items', 'schematic_parity'))
    if (report.get('drc_status') != 'FAIL' or report.get('exit_code') != 5
            or report.get('finding_count') != count or not native['unconnected_items']):
        raise ValueError('Baseline native DRC status/count mismatch')
    if report['report']['violations'] or report['report']['schematic_parity']:
        raise ValueError('Reservation requires connectivity-only failed baseline')
    for name, expected in report['input_sha256'].items():
        path = _path(root, paths['prior'].parent / name, exists=True)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Prior DRC input fingerprint changed')
    return paths, authority, intent, bundle, report


def _request(prior, pad_uuid):
    import pcbnew
    native = pcbnew.LoadBoard(str(prior))
    pads = [p for f in native.GetFootprints() for p in f.Pads() if p.m_Uuid.AsString() == pad_uuid]
    if len(pads) != 1:
        raise ValueError('Requested pad UUID not unique')
    pad = pads[0]
    return dict(uuid=pad_uuid, reference=pad.GetParentFootprint().GetReference(),
                pad=pad.GetNumber(), net=pad.GetNetname())


def prepare(root, original, current, prior, drc, intent, bundle, pad_uuid, output):
    output = _path(root, output)
    if output.exists():
        raise ValueError('Reservation preparation output must be fresh')
    paths, authority, intent, bundle, report = _inputs(root, dict(
        original=original, current=current, prior=prior, drc=drc, intent=intent, bundle=bundle))
    request = _request(paths['prior'], pad_uuid)
    proposal = reservation(root, paths['original'], paths['current'], paths['prior'], report,
                           request, intent, bundle.catalog)
    text, receipt = compose(paths['original'].read_text(), paths['current'].read_text(), proposal)
    for path, sha in authority.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != sha:
            raise ValueError('Reservation authority changed')
    if input_fingerprints(paths['current']) != proposal['current_files_sha256']:
        raise ValueError('Current settings changed before emission')
    output.mkdir()
    board = output / 'seed.kicad_pcb'
    board.write_text(text)
    receipt.update(board=str(board), authority_sha256=authority,
                   baseline_drc_sha256=digest(paths['drc'].read_text()),
                   baseline_board=str(paths['prior']), baseline_board_sha256=proposal['prior_sha256'],
                   settings_sha256={board.with_suffix(s).name:
                       proposal['source_files_sha256'][str(paths['original'].with_suffix(s))]
                       for s in ('.kicad_pro', '.kicad_dru')})
    receipt['identity'] = unchanged_placement(paths['original'], board)
    for name, document in (('proposal.json', proposal), ('seed-receipt.json', receipt)):
        (output / name).write_text(json.dumps(document, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser()
    for name in ('root', 'original', 'current', 'prior', 'drc', 'intent', 'bundle', 'pad_uuid', 'output'):
        parser.add_argument(name)
    args = parser.parse_args()
    print(json.dumps(prepare(**vars(args))))


if __name__ == '__main__':
    main()
