"""Source-backed pin capabilities and firmware configuration requirements."""
from __future__ import annotations

from copy import deepcopy


def validate_part_functions(catalog, part):
    for pin in part['pins']:
        functions = pin.get('functions', [])
        names = [function['name'] for function in functions]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate supported pin function')
        if functions and pin['type'] not in ('BIDIRECTIONAL', 'OUTPUT'):
            raise ValueError('Configured pin functions require a digital output-capable pin')
        for function in functions:
            catalog.vocabulary.member('pin-functions', function['name'])
            for evidence in function['evidence']:
                catalog._anchors(evidence)


def _capability(catalog, parts, ref, number, mode):
    catalog.vocabulary.member('pin-functions', mode)
    if ref not in parts:
        raise ValueError('Pin configuration references an absent component')
    pin = next((p for p in parts[ref]['pins'] if p['number'] == number), None)
    if pin is None or pin['type'] not in ('BIDIRECTIONAL', 'OUTPUT'):
        raise ValueError('Pin configuration requires a digital output-capable pin')
    supported = next((f for f in pin.get('functions', []) if f['name'] == mode), None)
    if supported is None:
        raise ValueError('Selected pin does not support the requested function')
    return supported


def validate_configurations(catalog, parts, configurations):
    """Validate the physical-pin requirements carried in the handoff."""
    seen = set()
    for config in configurations:
        key = config['ref'], config['pin']
        if key in seen:
            raise ValueError('Duplicate or conflicting physical pin configuration')
        seen.add(key)
        catalog.vocabulary.member('pin-states', config['initial_state'])
        if config['mode'] != 'GPIO_PUSH_PULL':
            raise ValueError('Unsupported firmware pin configuration mode')
        capability = _capability(catalog, parts, *key, config['mode'])
        if config['evidence'] != capability['evidence']:
            raise ValueError('Pin configuration evidence differs from selected pin capability')


def _physical_pin(expansion, request):
    key = request['instance'], request['port']
    if key not in expansion.port_nodes:
        raise ValueError('Pin configuration references an absent block port')
    node = expansion.port_nodes[key]
    pins = [pin for pin, local_node in expansion.pin_nodes.items() if local_node == node]
    if len(pins) != 1:
        raise ValueError('Configured block port must resolve to exactly one physical pin')
    return pins[0]


def configure_pins(expansion):
    """Resolve declared functions without inferring semantics from port names."""
    requirements = {}
    for request in expansion.graph.get('port_requirements', []):
        key = _physical_pin(expansion, request)
        _capability(expansion.catalog, expansion.parts, *key, request['function'])
        if key in requirements:
            raise ValueError('Duplicate or conflicting required pin function')
        requirements[key] = request['function']
    requirements.update(_block_requirements(expansion, requirements))
    configured = []
    for request in expansion.graph.get('pin_configurations', []):
        key = _physical_pin(expansion, request)
        if key in requirements and requirements[key] != request['mode']:
            raise ValueError('Pin configuration conflicts with a required pin function')
        capability = _capability(expansion.catalog, expansion.parts, *key, request['mode'])
        configured.append({'ref': key[0], 'pin': key[1], 'mode': request['mode'],
                           'initial_state': request['initial_state'],
                           'evidence': deepcopy(capability['evidence'])})
    validate_configurations(expansion.catalog, expansion.parts, configured)
    connections = {key: expansion.find(node) for key, node in expansion.pin_nodes.items()}
    validate_configured_drivers(expansion.parts, configured, connections)
    if configured:
        expansion.intent['pin_configurations'] = sorted(configured, key=lambda item: (item['ref'], item['pin']))


def _block_requirements(expansion, explicit):
    required = {}
    for iid, block in expansion.blocks.items():
        for port in block['ports']:
            function = port.get('required_function')
            if not function:
                continue
            expansion.catalog.vocabulary.member('pin-functions', function)
            net = expansion.find(expansion.port_nodes[iid, port['name']])
            matching = []
            for key, node in expansion.pin_nodes.items():
                if expansion.find(node) != net:
                    continue
                pin = next(p for p in expansion.parts[key[0]]['pins'] if p['number'] == key[1])
                if any(f['name'] == function for f in pin.get('functions', [])):
                    matching.append(key)
            if len(matching) != 1:
                raise ValueError('Required block-port function needs exactly one supported physical pin')
            key = matching[0]
            if key in explicit and explicit[key] != function:
                raise ValueError('Block-port function conflicts with explicit port requirement')
            if key in required and required[key] != function:
                raise ValueError('Conflicting block-port functions on one physical pin')
            required[key] = function
    return required


def validate_configured_drivers(parts, configurations, connections):
    configured = {(c['ref'], c['pin']) for c in configurations}
    nets = {}
    for ref, part in parts.items():
        for pin in part['pins']:
            key = ref, pin['number']
            if key not in connections:
                continue
            if key in configured or pin['type'] in ('OUTPUT', 'POWER_OUT'):
                nets.setdefault(connections[key], set()).add((ref, pin.get('same_net_as', pin['number'])))
    for config in configurations:
        net = connections.get((config['ref'], config['pin']))
        if net is None or len(nets.get(net, ())) != 1:
            raise ValueError('Configured GPIO conflicts with another output or has no connection')
