"""Exact sourced single-supply return pairs; physical POWER_IN types are unchanged."""
from copy import deepcopy
from .bootstrap import nominal, _evidence_shape


def validate_part(part, evidence):
    descriptor = part.get('single_supply_return')
    if descriptor is None:
        return None
    keys = {'positive_pin', 'negative_pin', 'capacitance_nominal', 'evidence'}
    if not isinstance(descriptor, dict) or set(descriptor) != keys:
        raise ValueError('Malformed single-supply return descriptor')
    positive, negative = (descriptor[k] for k in ('positive_pin', 'negative_pin'))
    pins = {pin['number']: pin for pin in part['pins']}
    if (positive == negative or positive not in pins or negative not in pins
            or any(pins[p]['type'] != 'POWER_IN' for p in (positive, negative))):
        raise ValueError('Single-supply pair must name distinct POWER_IN pins')
    anchors = descriptor['evidence']
    if not isinstance(anchors, list) or not anchors:
        raise ValueError('Single-supply pair requires source evidence')
    for anchor in anchors:
        evidence(anchor)
    quantity = descriptor['capacitance_nominal']
    if (not isinstance(quantity, dict) or quantity.get('basis') != 'DATASHEET'
            or 'value' not in quantity or 'evidence' not in quantity):
        raise ValueError('Single-supply bypass nominal requirement must be sourced')
    evidence(quantity['evidence'])
    nominal(quantity)
    return descriptor


def binding(parts, connections, ref, evidence=_evidence_shape):
    descriptor = validate_part(parts[ref], evidence)
    if descriptor is None:
        return None
    positive, negative = (descriptor[k] for k in ('positive_pin', 'negative_pin'))
    pn, nn = (connections.get((ref, pin)) for pin in (positive, negative))
    if pn is None or nn is None or pn == nn:
        raise ValueError('Single-supply pair must connect to distinct supply and return nets')
    caps = []
    for cref, part in sorted(parts.items()):
        if ('capacitor.ceramic' not in part['roles'] or len(part['pins']) != 2
                or any(pin['type'] != 'PASSIVE' for pin in part['pins'])):
            continue
        if {connections.get((cref, pin['number'])) for pin in part['pins']} != {pn, nn}:
            continue
        quantity = part.get('parameters', {}).get('capacitance', {})
        if nominal(quantity) != nominal(descriptor['capacitance_nominal']):
            continue
        if quantity.get('basis') != 'DATASHEET' or 'evidence' not in quantity:
            raise ValueError('Single-supply bypass capacitor lacks sourced nominal capacitance')
        evidence(quantity['evidence'])
        caps.append(cref)
    if not caps:
        raise ValueError('Single-supply pair lacks the specified nominal ceramic bypass')
    return {'component': ref, 'positive_pin': positive, 'negative_pin': negative,
            'supply_net': pn, 'return_net': nn, 'capacitor': caps[0], 'evidence': deepcopy(descriptor['evidence'])}


def project(parts, connections, evidence=_evidence_shape):
    return [binding(parts, connections, ref, evidence) for ref in sorted(parts)
            if parts[ref].get('single_supply_return') is not None]


def qualify(parts, connections, powered, grounds, evidence):
    receipts = project(parts, connections, evidence)
    for receipt in receipts:
        if (receipt['return_net'] not in grounds or receipt['supply_net'] not in powered
                or receipt['supply_net'] in grounds):
            raise ValueError('Single-supply pair requires an actual powered positive and board-source ground return')
    return {(row['component'], row['negative_pin']) for row in receipts}, receipts


def validate_projection(parts, connections, intent):
    if not any(part.get('single_supply_return') for part in parts.values()):
        if 'single_supply_returns' in intent:
            raise ValueError('Unexpected single-supply return receipts')
        return
    expected = project(parts, connections)
    if intent.get('single_supply_returns') != expected:
        raise ValueError('Single-supply return receipts differ from selected parts and actual topology')


def negative_pin(part, pin):
    descriptor = validate_part(part, _evidence_shape)
    return descriptor is not None and descriptor['negative_pin'] == pin
