"""Provenance-bound incomplete reservation eligibility, separate from final DRC."""
from pathlib import Path
import json
from pcbknowledge.v2.sexpr import parse
from pcbknowledge.v2.boardview import children
from .reservation_core import digest, copper_index, node_id


def _one(node, key):
    rows = children(node, key)
    if len(rows) != 1:
        raise ValueError('Expected one copper ' + key)
    return rows[0][1:]


def _ends(node):
    return {tuple(map(float, _one(node, key))) for key in ('start', 'end')}


def _released(current, receipt):
    index = copper_index(parse(current))
    removed = {row['uuid']: row['node'] for row in receipt['removed']}
    if any(uid not in index or index[uid] != node for uid, node in removed.items()):
        raise ValueError('Removed copper provenance differs from original routed source')
    result = {}
    for uid, node in index.items():
        if uid in removed or node[0] != 'segment':
            continue
        points = set()
        for old in removed.values():
            if old[0] != 'segment':
                continue
            if _one(node, 'net') == _one(old, 'net') and _one(node, 'layer') == _one(old, 'layer'):
                points.update(_ends(node) & _ends(old))
        if points:
            result[uid] = points
    return result


def classify_reservation(drc, receipt, current_text, baseline_text):
    if digest(baseline_text) != receipt['baseline_drc_sha256']:
        raise ValueError('Baseline DRC authority changed')
    baseline = json.loads(baseline_text)
    baseline_board = Path(receipt['baseline_board'])
    if baseline.get('board') != str(baseline_board):
        raise ValueError('Baseline board path differs from reservation authority')
    if baseline['input_sha256'].get(baseline_board.name) != receipt['baseline_board_sha256']:
        raise ValueError('Baseline board fingerprint differs from reservation authority')
    for suffix in ('.kicad_pro', '.kicad_dru'):
        expected = receipt['settings_sha256'][Path(receipt['board']).with_suffix(suffix).name]
        if baseline['input_sha256'].get(baseline_board.with_suffix(suffix).name) != expected:
            raise ValueError('Baseline settings differ from source authority')
    result = dict(status='INCOMPLETE', native_drc_status=drc.get('drc_status'),
                  routing_allowed=False, final_acceptance='NOT_RUN')
    board = Path(receipt['board'])
    if digest(current_text) != receipt['current_sha256']:
        raise ValueError('Reservation source changed')
    if baseline['report']['violations'] or baseline['report']['schematic_parity']:
        raise ValueError('Reservation baseline had other native findings')
    if drc.get('board') != str(board) or drc['input_sha256'].get(board.name) != receipt['output_sha256']:
        raise ValueError('DRC board fingerprint mismatch')
    settings = receipt['settings_sha256']
    if set(settings) != {board.with_suffix(s).name for s in ('.kicad_pro', '.kicad_dru')}:
        raise ValueError('Missing source settings authority')
    if any(drc['input_sha256'].get(name) != value for name, value in settings.items()):
        raise ValueError('DRC settings changed')
    report = drc['report']
    count = sum(len(report[k]) for k in ('violations', 'unconnected_items', 'schematic_parity'))
    if drc.get('drc_status') != 'FAIL' or drc.get('exit_code') != 5 or drc.get('finding_count') != count:
        raise ValueError('Native DRC status/count inconsistency')
    if report['schematic_parity']:
        return dict(result, reason='Native parity finding')
    released = _released(current_text, receipt)
    vias = {node_id(n): tuple(map(float, _one(n, 'at'))) for n in receipt['seed_nodes'] if n[0] == 'via'}
    if not vias or set(vias) != set(receipt['seed_via_uuids']):
        raise ValueError('Missing exact seed via provenance')
    seen = set()
    for finding in report['violations']:
        items = finding.get('items', [])
        if finding.get('severity') != 'warning' or len(items) != 1:
            return dict(result, reason='Other native finding')
        item = items[0]
        uid = item.get('uuid')
        position = (item.get('pos', {}).get('x'), item.get('pos', {}).get('y'))
        allowed = ((finding.get('type') == 'via_dangling' and vias.get(uid) == position) or
                   (finding.get('type') == 'track_dangling' and position in released.get(uid, set())))
        if not allowed or uid in seen:
            return dict(result, reason='Dangling finding lacks exact released/seed provenance')
        seen.add(uid)
    if not set(vias) <= seen:
        return dict(result, reason='Expected seed via incompleteness missing')
    return dict(result, routing_allowed=True, violation_count=len(report['violations']),
                unconnected_count=len(report['unconnected_items']), released_tracks=sorted(seen-set(vias)))
