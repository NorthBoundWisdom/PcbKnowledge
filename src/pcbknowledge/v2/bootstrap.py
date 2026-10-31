"""Typed floating-bootstrap source-path proof; never promotes floating nets."""
import math

FIELDS = {'kind', 'bootstrap_pin', 'switch_pin', 'supply_pin', 'ground_pin',
          'charge_path', 'capacitor_role', 'capacitance_nominal', 'evidence'}


def nominal(quantity):
    if not isinstance(quantity, dict) or quantity.get('unit') != 'F':
        raise ValueError('Bootstrap capacitance must use F')
    value = quantity.get('value', quantity.get('typ'))
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError('Explicit positive nominal capacitance required')
    return value


def validate_descriptor(part, descriptor, evidence):
    if not isinstance(descriptor, dict) or set(descriptor) != FIELDS:
        raise ValueError('Malformed bootstrap topology descriptor')
    if (descriptor['kind'] != 'FLOATING_BOOTSTRAP_SUPPLY'
            or descriptor['charge_path'] != 'INTERNAL_REGULATOR_DIODE'
            or descriptor['capacitor_role'] != 'capacitor.ceramic'):
        raise ValueError('Unsupported bootstrap topology')
    pins = {p['number']: p for p in part['pins']}
    numbers = [descriptor[key] for key in ('bootstrap_pin', 'switch_pin', 'supply_pin', 'ground_pin')]
    if any(not isinstance(number, str) or not number for number in numbers):
        raise ValueError('Bootstrap pin identifiers must be nonempty strings')
    if len(set(numbers)) != 4 or not set(numbers) <= set(pins):
        raise ValueError('Bootstrap endpoints must be four distinct actual part pins')
    types = [pins[number]['type'] for number in numbers]
    if types != ['POWER_IN', 'POWER_OUT', 'POWER_IN', 'GROUND']:
        raise ValueError('Bootstrap endpoints have incompatible source pin types')
    anchors = descriptor['evidence']
    if not isinstance(anchors, list) or not anchors:
        raise ValueError('Internal charge-path evidence is required')
    for anchor in anchors:
        evidence(anchor)
    quantity = descriptor['capacitance_nominal']
    if (not isinstance(quantity, dict) or quantity.get('basis') != 'DATASHEET'
            or 'value' not in quantity or 'evidence' not in quantity):
        raise ValueError('Bootstrap requirement must be source-backed nominal value')
    evidence(quantity['evidence'])
    nominal(quantity)



def validate_part(part, evidence):
    descriptors = part.get('bootstrap_supplies', [])
    if not isinstance(descriptors, list) or len(descriptors) > 8:
        raise ValueError('Malformed bootstrap descriptor collection')
    for descriptor in descriptors:
        validate_descriptor(part, descriptor, evidence)
    boot_pins = [descriptor['bootstrap_pin'] for descriptor in descriptors]
    if len(set(boot_pins)) != len(boot_pins):
        raise ValueError('Duplicate bootstrap supply declaration')
    return descriptors


def capacitor_binding(parts, pin_nets, ref, descriptor, evidence):
    """Validate exact floating decoupling, without claiming a source path."""
    boot, switch, supply, ground = (descriptor[k] for k in
                                    ('bootstrap_pin', 'switch_pin', 'supply_pin', 'ground_pin'))
    endpoints = {}
    for endpoint, net in pin_nets.items():
        endpoints.setdefault(net, set()).add(endpoint)
    keys = [(ref, p) for p in (boot, switch, supply, ground)]
    if any(key not in pin_nets for key in keys):
        raise ValueError('Bootstrap topology pin is disconnected')
    bn, sn, vn, gn = (pin_nets[key] for key in keys)
    if len({bn, sn, vn, gn}) != 4:
        raise ValueError('Bootstrap, switch, input and ground nets must remain distinct')
    candidates = []
    for cref, capacitor in sorted(parts.items()):
        if descriptor['capacitor_role'] not in capacitor['roles']:
            continue
        cpins = capacitor['pins']
        if len(cpins) != 2 or any(p['type'] != 'PASSIVE' for p in cpins):
            continue
        nodes = [(cref, p['number']) for p in cpins]
        if {pin_nets.get(n) for n in nodes} != {bn, sn}:
            continue
        quantity = capacitor.get('parameters', {}).get('capacitance', {})
        if nominal(quantity) != nominal(descriptor['capacitance_nominal']):
            raise ValueError('Bootstrap capacitor nominal value mismatches sourced requirement')
        if quantity.get('basis') != 'DATASHEET' or 'evidence' not in quantity:
            raise ValueError('Bootstrap capacitor nominal value lacks source evidence')
        evidence(quantity['evidence'])
        candidates.append((cref, nodes))
    if len(candidates) != 1:
        raise ValueError('Exactly one matching external bootstrap capacitor required')
    cref, cnodes = candidates[0]
    cap_boot = next(node for node in cnodes if pin_nets[node] == bn)
    if endpoints[bn] != {(ref, boot), cap_boot}:
        raise ValueError('Floating bootstrap supply must not power unrelated endpoints')
    return cref, vn, gn


def _evidence_shape(anchor):
    # Catalog validation separately resolves every nested source/page and verification.
    if (not isinstance(anchor, dict) or not isinstance(anchor.get('source'), str)
            or not anchor['source'].startswith('source:')
            or type(anchor.get('page')) is not int or anchor['page'] < 1):
        raise ValueError('Invalid bootstrap source evidence')


def decoupling(parts, pin_nets, ref, pin):
    """Return None for ordinary pins, otherwise recheck the exact bootstrap capacitor."""
    descriptors = validate_part(parts[ref], _evidence_shape)
    descriptor = next((d for d in descriptors if d['bootstrap_pin'] == pin), None)
    if descriptor is None:
        return None
    capacitor_binding(parts, pin_nets, ref, descriptor, _evidence_shape)
    return True


def qualify(parts, pin_nets, powered, grounds, evidence):
    """All references are expanded actual component identities, not design-specific names.

    `powered` and `grounds` are previously established conventional source-path sets.
    The caller retains ordinary source-path checks for every nonqualified pin.
    """
    qualified, receipts = set(), []
    for ref, part in sorted(parts.items()):
        descriptors = validate_part(part, evidence)
        boot_pins = [descriptor['bootstrap_pin'] for descriptor in descriptors]
        for descriptor in descriptors:
            boot = descriptor['bootstrap_pin']
            switch = descriptor['switch_pin']
            supply = descriptor['supply_pin']
            ground = descriptor['ground_pin']
            cref, vn, gn = capacitor_binding(parts, pin_nets, ref, descriptor, evidence)
            if vn not in powered or gn not in grounds:
                raise ValueError('Bootstrap internal charger lacks actual board supply/return')
            # No circular bootstrapping: every ordinary supply pin must already have a source.
            for pin in part['pins']:
                if pin['type'] == 'POWER_IN' and pin['number'] not in boot_pins:
                    if pin_nets.get((ref, pin['number'])) not in powered:
                        raise ValueError('Internal charger component has another unsupplied input')
            qualified.add((ref, boot))
            receipts.append({'component': ref, 'pin': boot, 'capacitor': cref,
                             'switch_pin': switch, 'supply_pin': supply, 'ground_pin': ground,
                             'result': 'PASS', 'scope': 'SOURCE_PATH_TOPOLOGY_ONLY',
                             'reason': 'Source-backed internal charging path plus exact floating capacitor topology'})
    return qualified, receipts
