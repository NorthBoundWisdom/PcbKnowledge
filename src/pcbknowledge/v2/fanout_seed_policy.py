"""Allow routing of an explicitly incomplete seed; never relabel native DRC PASS."""
from pathlib import Path


def classify_seed(drc, receipt):
    result = {'status': 'INCOMPLETE', 'native_drc_status': drc.get('drc_status'),
              'routing_allowed': False, 'final_acceptance': 'NOT_RUN'}
    board = Path(receipt['board'])
    if drc.get('board') != str(board) or drc.get('input_sha256', {}).get(board.name) != receipt['output_sha256']:
        raise ValueError('Seed DRC is not authenticated to emitted copper')
    expected_settings = receipt.get('settings_sha256', {})
    if set(expected_settings) != {board.with_suffix(s).name for s in ('.kicad_pro', '.kicad_dru')}:
        raise ValueError('Missing authoritative seed project/rules fingerprints')
    if any(drc['input_sha256'].get(name) != digest for name, digest in expected_settings.items()):
        raise ValueError('Seed DRC used changed project/rules')
    report = drc['report']
    count = sum(len(report[key]) for key in ('violations', 'unconnected_items', 'schematic_parity'))
    if drc.get('drc_status') != 'FAIL' or drc.get('exit_code') != 5 or drc.get('finding_count') != count:
        raise ValueError('Seed DRC process status or finding count is inconsistent')
    expected = set(receipt['seed_via_uuids'])
    if not expected or len(expected) != len(receipt['seed_via_uuids']):
        raise ValueError('Missing or duplicate seed via provenance')
    seen = set()
    for finding in report['violations']:
        if finding.get('type') != 'via_dangling' or finding.get('severity') != 'warning':
            return dict(result, reason='Other native geometric/manufacturing finding')
        items = finding.get('items', [])
        if len(items) != 1 or items[0].get('uuid') not in expected or items[0]['uuid'] in seen:
            return dict(result, reason='Dangling finding does not match unique new seed via')
        seen.add(items[0]['uuid'])
    if seen != expected or report['schematic_parity']:
        return dict(result, reason='Seed connectivity provenance/parity mismatch')
    return dict(result, routing_allowed=True, violation_count=len(report['violations']),
                unconnected_count=len(report['unconnected_items']),
                reason='Only exact newly seeded one-layer via connectivity warnings; final DRC remains strict')
