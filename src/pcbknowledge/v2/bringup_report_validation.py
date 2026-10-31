"""Structural and cross-field validation of unobserved bring-up reports."""
from .report_contracts import document_sha256, report_identity as envelope_identity, validate_schema


def report_identity(intent, graph):
    graph_hash = document_sha256(graph)
    if intent['block_graph_sha256'] != graph_hash:
        raise ValueError('Bring-up intent graph digest differs from the selected graph')
    return envelope_identity(intent)


def _observations(value):
    if isinstance(value, list):
        for child in value:
            _observations(child)
    elif isinstance(value, dict):
        for key, child in value.items():
            if key in ('result', 'a6', 'conditions_status', 'prerequisites_status') and child != 'NOT_RUN':
                raise ValueError('Bring-up reports contain plans, not hardware observations')
            _observations(child)


def _waveform(rail):
    from .bringup_waveform import _acquisition, _quantities, _source_bounds

    expected = rail['expected_waveform']
    protocol = expected['protocol']
    _source_provenance(expected['source_limits'])
    _quantities(protocol)
    _source_bounds(protocol, expected['source_limits'])
    _acquisition(protocol)
    test = rail['declared_test_location']
    reference = rail['declared_reference_location']
    supply = rail['declared_input_location']
    if (test['pin'] != '8' or reference['pin'] != '6' or supply['pin'] != '7'
            or len({test['ref'], reference['ref'], supply['ref']}) != 1):
        raise ValueError('Waveform report requires the exact same-device PH/GND/VIN terminals')
    if protocol['input_at'] != supply['ref'] + '.pin:' + supply['pin']:
        raise ValueError('Waveform protocol input differs from declared input location')


def _source_provenance(limits):
    from .bringup_waveform import SOURCE_FIELDS

    if set(limits) != set(SOURCE_FIELDS):
        raise ValueError('Waveform report source limits must contain the exact required parameters')
    for name, value in limits.items():
        unit = 's' if name.endswith('_duration_limit') else 'Hz' if name == 'frequency' else 'V'
        if value.get('basis') != 'DATASHEET' or not value.get('evidence') or value.get('unit') != unit:
            raise ValueError('Waveform source limits require cited datasheet quantities with matching units')
        if 'min' in value and 'max' in value and value['min'] > value['max']:
            raise ValueError('Waveform source limits are reversed')


def _voltage(expected):
    if expected['status'] == 'DECLARED':
        if expected['min'] > expected['max']:
            raise ValueError('Report voltage bounds are reversed')
        if 'nominal' in expected and not expected['min'] <= expected['nominal'] <= expected['max']:
            raise ValueError('Report nominal voltage is outside its declared interval')
    if 'contextual_expectation' in expected:
        _voltage(expected['contextual_expectation'])


def _rail(rail, report):
    if ('expected_voltage' in rail) == ('expected_waveform' in rail):
        raise ValueError('Report rail requires exactly one DC or waveform plan')
    expected = rail.get('expected_voltage', rail.get('expected_waveform'))
    conditional = expected.get('acceptance_type') in ('ENGINEERING_TEST_WINDOW', 'WAVEFORM_PROTOCOL')
    if conditional:
        if (not report.get('prerequisites') or report.get('prerequisites_status') != 'NOT_RUN'
                or expected.get('conditions_status') != 'NOT_RUN'):
            raise ValueError('Conditional plans require unobserved shared prerequisites and conditions')
    if 'expected_waveform' in rail:
        _waveform(rail)
    else:
        _voltage(expected)
    return expected['status'] == 'UNKNOWN'


def validate_bringup_report(report, schemas):
    validate_schema(report, 'bringup', schemas)
    _observations(report)
    if report['identity']['bundle_commit'] != report['bundle_commit']:
        raise ValueError('Report identity and top-level bundle commit differ')
    names = [row['net'] for row in report['rails']]
    if len(names) != len(set(names)):
        raise ValueError('Report has duplicate physical rail names')
    unresolved = [row['net'] for row in report['rails'] if _rail(row, report)]
    if report['unresolved_rail_ranges'] != unresolved:
        raise ValueError('Unresolved rail list must exactly match unknown measurement plans')
    if report['range_coverage'] != ('UNKNOWN' if unresolved else 'COMPLETE'):
        raise ValueError('Range coverage disagrees with unknown measurement plans')
    if ('prerequisites' in report) != ('prerequisites_status' in report):
        raise ValueError('Shared prerequisites and their observation status must occur together')
    return report
