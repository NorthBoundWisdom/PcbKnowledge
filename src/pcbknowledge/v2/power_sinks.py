"""Typed external-load returns and their catalog-backed supply-port provenance."""
from __future__ import annotations


def _pin(part, number):
    match = next((pin for pin in part['pins'] if pin['number'] == number), None)
    if match is None:
        raise ValueError('External load references an absent physical pin')
    return match


def _local_port(block, component, part, number, kind):
    pin = _pin(part, number)
    endpoints = {component + '.pin:' + number, component + '.pin:' + pin.get('name', number)}
    kinds = {port['name']: port['kind'] for port in block['ports']}
    matches = [(net['name'], endpoint[5:]) for net in block['nets']
               if endpoints.intersection(net['connect']) for endpoint in net['connect']
               if endpoint.startswith('port:') and kinds.get(endpoint[5:]) == kind]
    if len(matches) != 1:
        raise ValueError('External load pin must map to exactly one required block port')
    return matches[0]


def validate_block_loads(catalog, block, candidates):
    seen = set()
    for load in block.get('external_loads', []):
        ref, supply, returned = (load[key] for key in ('connector', 'supply_pin', 'return_pin'))
        if ref not in candidates or supply == returned or (ref, returned) in seen:
            raise ValueError('Invalid or duplicate external-load connector mapping')
        seen.add((ref, returned))
        for part in candidates[ref]:
            if 'connector.header' not in part['roles']:
                raise ValueError('External load requires a source-backed connector part')
            if any(_pin(part, number)['type'] != 'PASSIVE' for number in (supply, returned)):
                raise ValueError('External-load connector pins must be passive physical terminals')
            supply_net, _ = _local_port(block, ref, part, supply, 'POWER_IN')
            return_net, _ = _local_port(block, ref, part, returned, 'PASSIVE')
            if supply_net == return_net:
                raise ValueError('External-load supply and return must be distinct block nets')


def _selected_part(catalog, parts, block, local, expanded):
    component = next((item for item in block['components'] if item['ref'] == local), None)
    if component is None or expanded not in parts:
        raise ValueError('External-load provenance references an absent component')
    if parts[expanded]['id'] not in {p['id'] for p in catalog._candidates(component['select'])}:
        raise ValueError('External-load provenance differs from the selected catalog part')
    return parts[expanded]


def validate_loads(catalog, parts, nets, loads, dependencies):
    connections = {(p['ref'], p['pin']): net['name'] for net in nets for p in net['pins']}
    ground = {connections.get((ref, p['number'])) for ref, part in parts.items()
              for p in part['pins'] if p['type'] == 'GROUND'} - {None}
    seen = set()
    for load in loads:
        block = catalog.get(load['block'], 'block')
        declaration = {key: load[key] for key in ('supply_pin', 'return_pin')}
        declaration['connector'] = load['local_connector']
        if load['block'] not in dependencies or declaration not in block.get('external_loads', []):
            raise ValueError('External-load declaration differs from its catalog block')
        part = _selected_part(catalog, parts, block, load['local_connector'], load['connector'])
        validate_block_loads(catalog, {**block, 'external_loads': [declaration]},
                             {load['local_connector']: [part]})
        key = load['connector'], load['return_pin']
        if key in seen:
            raise ValueError('Duplicate physical external-load return')
        seen.add(key)
        supply = connections.get((load['connector'], load['supply_pin']))
        returned = connections.get(key)
        if supply is None or returned is None or supply == returned or supply in ground:
            raise ValueError('External load requires a distinct connected non-ground supply')
        provider = load['provider']
        source = catalog.get(provider['block'], 'block')
        if provider['block'] not in dependencies:
            raise ValueError('Supply provider is outside the declared catalog dependencies')
        source_part = _selected_part(catalog, parts, source, provider['local_component'], provider['ref'])
        _, port = _local_port(source, provider['local_component'], source_part, provider['pin'], 'POWER_OUT')
        if port != provider['port'] or connections.get((provider['ref'], provider['pin'])) != supply:
            raise ValueError('Supply provider does not match the catalog POWER_OUT port and physical net')
        if _pin(source_part, provider['pin'])['type'] in ('GROUND', 'POWER_SINK', 'NO_CONNECT'):
            raise ValueError('Supply provider has an incompatible physical pin type')


def _provider(expansion, supply_node):
    for iid, block in sorted(expansion.blocks.items()):
        for port in sorted(block['ports'], key=lambda item: item['name']):
            node = expansion.port_nodes.get((iid, port['name']))
            if port['kind'] != 'POWER_OUT' or node is None or expansion.find(node) != supply_node:
                continue
            for (ref, pin), local_node in sorted(expansion.pin_nodes.items()):
                if local_node != node:
                    continue
                local = ref[len(iid) + 1:]
                if local not in expansion.local_parts[iid]:
                    continue
                return {'block': block['id'], 'local_component': local, 'ref': ref,
                        'pin': pin, 'port': port['name']}
    raise ValueError('External-load supply lacks a catalog POWER_OUT provider on its actual net')


def derive_loads(expansion):
    loads = []
    powered = {expansion.find(expansion.port_nodes[iid, port['name']])
               for iid, block in expansion.blocks.items() for port in block['ports']
               if port['kind'] == 'POWER_OUT' and (iid, port['name']) in expansion.port_nodes}
    for iid, block in sorted(expansion.blocks.items()):
        for item in block.get('external_loads', []):
            ref = iid + '_' + item['connector']
            key = ref, item['supply_pin']
            if key not in expansion.pin_nodes:
                raise ValueError('External-load connector supply pin is absent')
            returned = ref, item['return_pin']
            if returned not in expansion.pin_nodes or expansion.find(expansion.pin_nodes[returned]) in powered:
                raise ValueError('External-load return is absent or shorted to a POWER_OUT block port')
            return_net = getattr(expansion, 'resolved', {}).get(expansion.pin_nodes[returned])
            if return_net in getattr(expansion, 'powered', set()):
                raise ValueError('External-load return is shorted to a reachable board supply')
            supply_node = expansion.find(expansion.pin_nodes[key])
            loads.append({'block': block['id'], 'local_connector': item['connector'], 'connector': ref,
                          'supply_pin': item['supply_pin'], 'return_pin': item['return_pin'],
                          'provider': _provider(expansion, supply_node)})
    if loads:
        validate_loads(expansion.catalog, expansion.parts, expansion.intent['nets'], loads,
                       expansion.intent['dependencies'])
        expansion.intent['external_loads'] = loads


def sink_checks(parts, nets, loads):
    if not loads and not any(pin['type'] == 'POWER_SINK' for part in parts.values() for pin in part['pins']):
        return []
    connections = {(p['ref'], p['pin']): net['name'] for net in nets for p in net['pins']}
    approved = {connections.get((load['connector'], load['return_pin'])) for load in loads} - {None}
    supplies = {connections.get((load['connector'], load['supply_pin'])) for load in loads} - {None}
    indexed = {net['name']: [(endpoint['ref'], _pin(parts[endpoint['ref']], endpoint['pin']))
                             for endpoint in net['pins']] for net in nets}
    checks = []
    for load in loads:
        net = connections.get((load['connector'], load['return_pin']))
        passed = any(pin['type'] == 'POWER_SINK' for _, pin in indexed.get(net, []))
        checks.append({'id': 'external_load:' + load['connector'] + ':' + load['return_pin'],
                       'result': 'PASS' if passed else 'FAIL',
                       'reason': 'Declared external-load return is connected to a physical power sink'})
    for ref, part in sorted(parts.items()):
        for pin in part['pins']:
            if pin['type'] != 'POWER_SINK' or (ref, pin['number']) not in connections:
                continue
            net = connections[ref, pin['number']]
            logical = ref, pin.get('same_net_as', pin['number'])
            safe = all(other['type'] == 'PASSIVE' or
                       (other['type'] == 'POWER_SINK' and
                        (other_ref, other.get('same_net_as', other['number'])) == logical)
                       for other_ref, other in indexed[net])
            checks.append({'id': 'power_sink:' + ref + ':' + pin['number'],
                           'result': 'PASS' if net in approved and net not in supplies and safe else 'FAIL',
                           'reason': 'Power sink has a supplied external-load return without active-pin shorts'})
    return checks
