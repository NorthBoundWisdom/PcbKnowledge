"""Explicit conditional engineering test windows bound to expanded physical rails."""
from copy import deepcopy
import math


def _endpoint(text, connections, nets, expected_class):
    ref, separator, pin = text.partition('.pin:')
    if not separator or not ref or not pin or (ref, pin) not in connections:
        raise ValueError('Bring-up endpoint is not an exact connected physical pin: ' + text)
    name = connections[ref, pin]
    if nets[name]['class'] != expected_class:
        raise ValueError('Bring-up endpoint requires ' + expected_class + ': ' + text)
    return name


def _window(quantity):
    if quantity.get('basis') != 'ENGINEERING_DEFAULT' or quantity.get('unit') != 'V':
        raise ValueError('Bring-up windows are engineering voltage test decisions')
    bounds = [quantity.get(key) for key in ('min', 'max')]
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in bounds) or bounds[0] > bounds[1]:
        raise ValueError('Bring-up requires finite ordered min/max')
    if not quantity.get('note') or not quantity.get('conditions'):
        raise ValueError('Bring-up requires explicit operating conditions and decision note')
    for value in quantity['conditions'].values():
        if type(value.get('value')) not in (int, float) or not math.isfinite(value['value']) or not value.get('unit'):
            raise ValueError('Bring-up operating conditions require finite quantities')


def validate_bringup(intent, catalog=None):
    declaration = intent.get('bringup')
    if declaration is None:
        return {}
    if not declaration.get('prerequisites') or any(not isinstance(v, str) or not v.strip()
                                                  for v in declaration['prerequisites']):
        raise ValueError('Bring-up requires shared prerequisite measurement procedures')
    nets = {row['name']: row for row in intent['nets']}
    connections = {}
    for name, net in nets.items():
        for pin in net['pins']:
            key = pin['ref'], pin['pin']
            if key in connections:
                raise ValueError('Ambiguous physical pin in bring-up conditions')
            connections[key] = name
    result = {}
    for row in declaration['rails']:
        name = _endpoint(row['at'], connections, nets, 'POWER')
        if name in result:
            raise ValueError('Duplicate or conflicting bring-up window for rail: ' + name)
        if 'reference_at' in row:
            _endpoint(row['reference_at'], connections, nets, 'GROUND')
        if ('expected_voltage' in row) == ('waveform' in row):
            raise ValueError('Bring-up requires exactly one DC or waveform contract')
        if 'waveform' in row:
            from .bringup_waveform import validate_waveform
            validate_waveform(row, intent, lambda text, kind: _endpoint(text, connections, nets, kind), catalog)
        else:
            _window(row['expected_voltage'])
        result[name] = row
    return result


def bringup_sources(declaration):
    sources = set()
    def walk(value):
        if isinstance(value, dict):
            if 'source' in value and 'page' in value:
                sources.add(value['source'])
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(declaration)
    return sources


def project_bringup(graph, intent, catalog, used):
    if 'bringup' not in graph:
        return
    declaration = deepcopy(graph['bringup'])
    name = 'design-intent.schema.json'
    definition = catalog.schemas.load(name)['$defs']['bringup']
    catalog.schemas.check(definition, name)
    catalog.schemas.apply(declaration, definition, name)
    catalog.vocabulary.document(declaration)
    validate_bringup({**intent, 'bringup': declaration}, catalog)
    catalog._anchors(declaration)
    used.update(bringup_sources(declaration))
    intent['bringup'] = declaration


def apply_test_windows(report, intent, *, locate, catalog=None):
    declarations = validate_bringup(intent, catalog)
    if declarations:
        report['prerequisites'] = deepcopy(intent['bringup']['prerequisites'])
        report['prerequisites_status'] = 'NOT_RUN'
    for rail in report['rails']:
        row = declarations.get(rail['net'])
        if row is None:
            continue
        if 'waveform' in row:
            _apply_waveform(rail, row, intent, catalog, locate)
            continue
        quantity = deepcopy(row['expected_voltage'])
        prior = rail['expected_voltage']
        if 'nominal' in prior and not quantity['min'] <= prior['nominal'] <= quantity['max']:
            raise ValueError('Engineering window conflicts with declared nominal voltage')
        expected = {'status': 'DECLARED', 'acceptance_type': 'ENGINEERING_TEST_WINDOW',
                    'conditions_status': 'NOT_RUN', 'prerequisites': deepcopy(row.get('prerequisites', [])),
                    'basis': quantity['basis'], 'unit': 'V', 'min': quantity['min'], 'max': quantity['max'],
                    'conditions': quantity['conditions'], 'decision_note': quantity['note'],
                    'contextual_expectation': deepcopy(prior), 'declarations': [{
                        'origin': 'intent.bringup.' + row['at'], 'quantity': quantity}],
                    'supporting_evidence': deepcopy(row.get('supporting_evidence', []))}
        if 'nominal' in prior:
            expected['nominal'] = prior['nominal']
        rail['expected_voltage'] = expected
        for key, destination in (('at', 'declared_test_location'), ('reference_at', 'declared_reference_location')):
            if key in row:
                ref, _, pin = row[key].partition('.pin:')
                rail[destination] = locate({'ref': ref, 'pin': pin})
    unresolved = [row['net'] for row in report['rails']
                  if row.get('expected_voltage', row.get('expected_waveform', {})).get('status') == 'UNKNOWN']
    report['range_coverage_note'] = 'Coverage describes declared measurement plans, not measured compliance.'
    report.update(range_coverage='UNKNOWN' if unresolved else 'COMPLETE', unresolved_rail_ranges=unresolved)
    return report


def _apply_waveform(rail, row, intent, catalog, locate):
    from .bringup_waveform import source_limits
    rail['expected_waveform'] = {'status': 'DECLARED', 'acceptance_type': 'WAVEFORM_PROTOCOL',
        'protocol': deepcopy(row['waveform']), 'conditions_status': 'NOT_RUN',
        'source_limits': deepcopy(source_limits(row, intent, catalog)),
        'prerequisites': deepcopy(row.get('prerequisites', [])),
        'supporting_evidence': deepcopy(row.get('supporting_evidence', []))}
    rail.pop('expected_voltage', None)
    for source, dest in ((row['at'], 'declared_test_location'),
                         (row['reference_at'], 'declared_reference_location'),
                         (row['waveform']['input_at'], 'declared_input_location')):
        ref, _, pin = source.partition('.pin:')
        rail[dest] = locate({'ref': ref, 'pin': pin})
