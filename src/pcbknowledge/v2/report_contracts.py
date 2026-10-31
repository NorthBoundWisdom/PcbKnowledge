"""Owned report envelopes and consistency checks, separate from geometry measurements."""
from __future__ import annotations

import hashlib
from pcbknowledge.serialization import canonical_json


def document_sha256(value):
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def validate_schema(report, name, schemas):
    definitions = {'layout': 'layoutReport', 'bringup': 'bringupReport', 'drc': 'drcReport'}
    if name not in definitions:
        raise ValueError('Unknown owned report contract')
    reference = 'envelope.schema.json#/$defs/' + definitions[name]
    schema, filename = schemas.resolve(reference, 'envelope.schema.json')
    schemas.check(schema, filename)
    schemas.apply(report, schema, filename)


def report_identity(intent, *, board_sha256=None):
    return {'bundle_commit': intent['bundle_commit'], 'block_graph_sha256': intent['block_graph_sha256'],
            'intent_sha256': document_sha256(intent), 'board_sha256': board_sha256}


def combined_result(checks):
    states = {row['result'] for row in checks}
    return 'FAIL' if 'FAIL' in states else 'NOT_CHECKABLE' if 'NOT_CHECKABLE' in states else 'PASS'


def _measurement_consistency(check):
    if check['kind'] == 'GUARD_RING' and 'surfaces' in check:
        layers = [row.get('layer') for row in check['surfaces']]
        if len(layers) != len(set(layers)):
            raise ValueError('Duplicate guard surface')
        for surface in check['surfaces']:
            _measurement_consistency({'kind': 'GUARD_RING', **surface})
    if check['kind'] == 'GUARD_RING' and 'protected' in check:
        passed = (check['connected_to_guard_pad'] and check['protected']
                  and check['min_width_mm'] >= check['required_width_mm'])
        if check['result'] != ('PASS' if passed else 'FAIL'):
            raise ValueError('Guard result disagrees with closed-ring measurements')
    if 'surfaces' in check and check['result'] != combined_result(check['surfaces']):
        raise ValueError('Guard surface summary disagrees with measurements')
    if check['kind'] != 'RETURN_PATH' or 'segments' not in check:
        return
    segments = check['segments']
    if not segments and not check.get('arcs'):
        raise ValueError('Return report has no measured conductor')
    for row in segments + check.get('arcs', []):
        if row['signal_layer'] == row['reference_layer'] or row['width_mm'] <= 0:
            raise ValueError('Return report requires opposite layers and positive width')
    indices = [row['segment'] for row in segments]
    if len(indices) != len(set(indices)):
        raise ValueError('Duplicate measured return segment')
    failed = [row['segment'] for row in segments if not row['covered']]
    if check['failed_segments'] != failed:
        raise ValueError('Return failed-segment summary disagrees with measurements')
    if check['result'] != ('FAIL' if failed else 'PASS'):
        raise ValueError('Return result disagrees with measurements')
    arcs = [row['arc'] for row in check.get('arcs', [])]
    if len(arcs) != len(set(arcs)):
        raise ValueError('Duplicate measured return arc')


def _finding_sequence(checks):
    unindexed = [row['kind'] for row in checks if 'index' not in row]
    expected = ['IDENTITY']
    if checks[0]['result'] == 'PASS':
        expected += ['BOARD_ENVELOPE', 'BOARD_THICKNESS', 'COPPER_LAYER_COUNT',
                     'COMPONENT_HEIGHT', 'ASSEMBLY_SIDE']
    else:
        expected += ['CONSTRAINTS']
        if len(checks) < 2 or checks[1]['result'] != 'NOT_CHECKABLE':
            raise ValueError('Identity failure requires unmeasured constraints')
    if unindexed and unindexed[-1] == 'GEOMETRY':
        expected += ['GEOMETRY']
    if unindexed != expected:
        raise ValueError('Layout report omits or duplicates required board findings')


def validate_layout_report(report, schemas, *, intent=None, board_sha256=None):
    validate_schema(report, 'layout', schemas)
    if report['result'] != combined_result(report['checks']) or report['status'] != report['result']:
        raise ValueError('Layout result disagrees with findings')
    checks = report['checks']
    rules = report['constraints']
    if not checks or checks[0]['kind'] != 'IDENTITY':
        raise ValueError('Layout report must begin with identity check')
    _finding_sequence(checks)
    indexed = [row for row in checks if 'index' in row]
    indices = [row['index'] for row in indexed]
    if indices != list(range(len(indices))):
        raise ValueError('Layout rule indexes must be complete and ordered')
    if checks[0]['result'] == 'PASS' and len(indexed) != len(rules):
        raise ValueError('Layout report omits copied input rules')
    if any(row['kind'] != rules[row['index']]['kind'] for row in indexed):
        raise ValueError('Layout measurement kind differs from copied rule')
    if checks[0]['result'] != 'PASS' and indexed:
        raise ValueError('Layout cannot measure rules after identity failure')
    if board_sha256 is not None and report['identity']['board_sha256'] != board_sha256:
        raise ValueError('Layout report is bound to different board bytes')
    if intent is not None:
        if rules != intent['layout']:
            raise ValueError('Copied report constraints differ from intent')
        if report['identity'] != report_identity(intent, board_sha256=report['identity']['board_sha256']):
            raise ValueError('Layout report is bound to different intent')
        if checks[0]['result'] == 'PASS':
            if len(indexed) != len(intent['layout']):
                raise ValueError('Layout report omits intent rules')
            if any(row['kind'] != rule['kind'] for row, rule in zip(indexed, intent['layout'])):
                raise ValueError('Layout report rule kind disagrees with intent')
    from .report_measurements import scalar_consistency
    for check in checks:
        _measurement_consistency(check)
        scalar_consistency(check, rules[check['index']] if 'index' in check else None)
    return report
