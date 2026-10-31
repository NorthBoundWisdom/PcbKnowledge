"""Read-only bring-up plan from resolved physical nets and explicit voltage declarations."""
from __future__ import annotations

from copy import deepcopy
import math


def _quantity(value, origin):
    if not isinstance(value, dict) or value.get('unit') != 'V' or value.get('status'):
        return None
    numbers = {key: value[key] for key in ('value', 'min', 'max') if key in value}
    if not numbers or any(isinstance(v, bool) or not isinstance(v, (int, float))
                          or not math.isfinite(v) for v in numbers.values()):
        return None
    if 'min' in numbers and 'max' in numbers and numbers['min'] > numbers['max']:
        raise ValueError('Reversed declared bring-up voltage range')
    return {'origin': origin, 'quantity': deepcopy(value)}


def _physical_index(intent, catalog):
    components = {row['ref']: row for row in intent['components']}
    nets = {(pin['ref'], pin['pin']): net['name'] for net in intent['nets'] for pin in net['pins']}
    parts = {ref: catalog.get(row['part'], 'part') for ref, row in components.items()}
    return components, parts, nets


def _port_pins(instance, block, parts, nets):
    result = {}
    for local in block['nets']:
        ports = [item[5:] for item in local['connect'] if item.startswith('port:')]
        pins = []
        for endpoint in local['connect']:
            if endpoint.startswith('port:'):
                continue
            ref, separator, pin = endpoint.partition('.pin:')
            ref = instance['id'] + '_' + ref
            if not separator or ref not in parts:
                raise ValueError('Bring-up block physical endpoint is unresolved')
            matches = [row for row in parts[ref]['pins'] if pin in (row['name'], row['number'])]
            for match in matches:
                key = ref, match['number']
                if key not in nets:
                    raise ValueError('Bring-up block pin is absent from expanded intent')
                pins.append({'ref': ref, 'pin': match['number'], 'net': nets[key]})
            if not matches:
                raise ValueError('Bring-up block endpoint has no physical pin')
        for port in ports:
            if port in result or len({row['net'] for row in pins}) != 1:
                raise ValueError('Bring-up block port is ambiguous or lacks physical pins')
            result[port] = pins
    return result


def _declared_voltages(instances, catalog, parts, nets):
    candidates, ports_by_instance = {}, {}
    for instance in instances:
        block = catalog.get(instance['block'], 'block')
        ports = _port_pins(instance, block, parts, nets)
        ports_by_instance[instance['id']] = ports
        outputs = [row['name'] for row in block['ports'] if row['kind'] == 'POWER_OUT']
        # A generic output_voltage is unambiguous only for one physical output rail.
        output_nets = {row['net'] for port in outputs for row in ports.get(port, [])}
        declaration = _quantity(instance['parameters'].get('output_voltage'),
                                'graph.instances.' + instance['id'] + '.parameters.output_voltage')
        if len(output_nets) == 1 and declaration:
            candidates.setdefault(next(iter(output_nets)), []).append(declaration)
    for ref, part in parts.items():
        outputs = {nets[(ref, row['number'])] for row in part['pins']
                   if row['type'] == 'POWER_OUT' and (ref, row['number']) in nets}
        declaration = _quantity(part.get('parameters', {}).get('output_voltage'),
                                part['id'] + '.parameters.output_voltage')
        if len(outputs) == 1 and declaration:
            candidates.setdefault(next(iter(outputs)), []).append(declaration)
    return candidates, ports_by_instance


def _brief_voltages(brief, instances, catalog, ports, candidates):
    for group in ('sources', 'rails'):
        for supply in brief.get('power', {}).get(group, []):
            declaration = _quantity(supply.get('voltage'), 'brief.power.' + group + '.' + supply['id'])
            matches = [row for row in instances if supply.get('function') in row['requirements']]
            if not declaration or len(matches) != 1:
                continue
            instance = matches[0]
            block = catalog.get(instance['block'], 'block')
            outputs = [row['name'] for row in block['ports'] if row['kind'] == 'POWER_OUT']
            names = {pin['net'] for port in outputs for pin in ports[instance['id']].get(port, [])}
            if len(names) == 1:
                candidates.setdefault(next(iter(names)), []).append(declaration)


def _expected(candidates):
    ranges = [row['quantity'] for row in candidates if {'min', 'max'} <= row['quantity'].keys()]
    nominal = {row['quantity']['value'] for row in candidates if 'value' in row['quantity']}
    if len(nominal) > 1:
        return {'status': 'UNKNOWN', 'reason': 'Conflicting declared nominal output voltages'}
    result = {'unit': 'V', 'declarations': candidates}
    if nominal:
        result['nominal'] = next(iter(nominal))
    if not ranges:
        result.update(status='UNKNOWN', reason='No explicit minimum and maximum output voltage declared')
        return result
    # Do not combine unrelated bounds into a newly invented tolerance.
    bounds = {(row['min'], row['max']) for row in ranges}
    if len(bounds) != 1:
        result.update(status='UNKNOWN', reason='Multiple differing output voltage ranges require review')
        return result
    lower, upper = next(iter(bounds))
    if nominal and not lower <= next(iter(nominal)) <= upper:
        result.update(status='UNKNOWN', reason='Nominal output lies outside declared range')
        return result
    result.update(status='DECLARED', min=lower, max=upper)
    return result


def _location(pin, board):
    result = deepcopy(pin)
    if board is None:
        result.update(location_status='UNKNOWN', reason='No placed board supplied; physical terminal identified only')
        return result
    pads = board['footprints'].get(pin['ref'], {}).get('pads', {}).get(pin['pin'], [])
    if not pads:
        result.update(location_status='UNKNOWN', reason='Physical terminal is absent from placed board')
    else:
        result.update(location_status='LOCATED', pad_centers_mm=[row['at'] for row in pads])
    return result


def make_bringup(intent, graph, brief, catalog, *, board=None):
    """Inputs are already validated; this projection never modifies source records."""
    if intent.get('status') != 'EXPANDED' or graph['brief'] != brief['id'] or intent['brief_id'] != brief['id']:
        raise ValueError('Bring-up needs expanded intent and matching graph/brief')
    _, parts, nets = _physical_index(intent, catalog)
    candidates, ports = _declared_voltages(graph['instances'], catalog, parts, nets)
    _brief_voltages(brief, graph['instances'], catalog, ports, candidates)
    rails = []
    for net in sorted(intent['nets'], key=lambda row: row['name']):
        if net['class'] != 'POWER':
            continue
        rails.append({'net': net['name'], 'expected_voltage': _expected(candidates.get(net['name'], [])),
                      'test_locations': [_location(pin, board) for pin in net['pins']], 'result': 'NOT_RUN'})
    programming = []
    for instance in graph['instances']:
        block = catalog.get(instance['block'], 'block')
        if block['category'] != 'digital.debug':
            continue
        pinout = [{'signal': port, **_location(pin, board)}
                  for port, pins in sorted(ports[instance['id']].items()) for pin in pins]
        programming.append({'instance': instance['id'], 'block': block['id'], 'pinout': pinout,
                            'result': 'NOT_RUN'})
    functions = [{'id': row['id'], 'description': row['description'], 'count': row['count'],
                  'requirements': deepcopy(row['requirements']), 'parameters': deepcopy(row['parameters']),
                  'result': 'NOT_RUN'} for row in brief['functions']]
    unresolved = [row['net'] for row in rails if row['expected_voltage']['status'] == 'UNKNOWN']
    report = {'schema': 'pcbknowledge.bringup.v2', 'brief': brief['id'], 'bundle_commit': intent['bundle_commit'],
            'rails': rails, 'programming': programming, 'functional_tests': functions, 'a6': 'NOT_RUN',
            'range_coverage': 'UNKNOWN' if unresolved else 'COMPLETE', 'unresolved_rail_ranges': unresolved,
            'test_location_note': 'Terminal coordinates identify probes; physical probe accessibility is not proven.'}
    from .bringup_contract import apply_test_windows
    return apply_test_windows(report, intent, locate=lambda pin: _location(pin, board))


def render_bringup(report):
    """Human-readable checklist; observations stay unchecked until owner bring-up."""
    lines = ['# Bring-up checklist: ' + report['brief'], '',
             'Bundle: `' + report['bundle_commit'] + '`', '',
             'Hardware observations: NOT_RUN. Voltage range coverage: ' + report['range_coverage'] + '.', '',
             '## Rails', '', report['test_location_note'], '']
    if report.get('prerequisites'):
        lines.extend(['## Shared prerequisites (NOT_RUN)', ''])
        lines.extend('- [ ] ' + item for item in report['prerequisites'])
        lines.append('')
    for rail in report['rails']:
        value = rail['expected_voltage']
        expected = (f"{value['min']} to {value['max']} V" if value['status'] == 'DECLARED'
                    else 'UNKNOWN: ' + value['reason'])
        lines.append('- [ ] ' + rail['net'] + ': ' + expected)
        if value.get('acceptance_type') == 'ENGINEERING_TEST_WINDOW':
            lines.append('  - [ ] Establish all operating conditions before interpreting measurements.')
            lines.append('  Engineering test window; conditions NOT_RUN.')
            lines.append('  Conditions: ' + str(value['conditions']))
            lines.extend('  - [ ] ' + item for item in value['prerequisites'])
            for key in ('declared_test_location', 'declared_reference_location'):
                if key in rail:
                    lines.append('  ' + key + ': ' + str(rail[key]))
        if 'nominal' in value:
            lines.append(f"  Declared nominal: {value['nominal']} V (not a tolerance range).")
        for pin in rail['test_locations']:
            coordinate = ' ' + str(pin['pad_centers_mm']) + ' mm' if 'pad_centers_mm' in pin else ''
            lines.append('  - Terminal ' + pin['ref'] + '.' + pin['pin'] + coordinate)
        for declaration in value.get('declarations', []):
            lines.append('  - Declaration: ' + declaration['origin'] + ' ' + str(declaration['quantity']))
    lines.extend(['', '## Programming connector pinout', ''])
    for connector in report['programming']:
        lines.append('- [ ] ' + connector['instance'] + ': programming/debug functional check')
        for pin in connector['pinout']:
            lines.append('  - ' + pin['ref'] + '.' + pin['pin'] + ': ' + pin['signal'] + ' / ' + pin['net'])
    lines.extend(['', '## Required functional tests', ''])
    for item in report['functional_tests']:
        lines.append('- [ ] ' + item['id'] + ': ' + item['description'] + ' (count ' + str(item['count']) + ')')
        lines.extend('  - ' + requirement for requirement in item['requirements'])
        if item['parameters']:
            lines.append('  - Declared parameters: ' + str(item['parameters']))
    return '\n'.join(lines) + '\n'
