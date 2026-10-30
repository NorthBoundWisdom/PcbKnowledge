"""Resolve a fuse-entry proximity rule from physical pins on one electrical net."""


def fuse_entry_bindings(ref, parts, nets):
    if 'protection.fuse' not in parts[ref]['roles']:
        raise ValueError('Fuse-entry binding requires a protection.fuse component')
    candidates = set()
    for net in nets:
        endpoints = []
        for endpoint in net['pins']:
            part = parts[endpoint['ref']]
            pin = next(p for p in part['pins'] if p['number'] == endpoint['pin'])
            endpoints.append((endpoint['ref'], part, pin))
        if net['class'] == 'GROUND' or any(pin['type'] == 'GROUND' for _, _, pin in endpoints):
            continue
        fuse_pins = [pin['number'] for component, _, pin in endpoints
                     if component == ref and pin['type'] == 'PASSIVE']
        connector_pins = [(component, pin['number']) for component, part, pin in endpoints
                          if component != ref and 'connector.header' in part['roles'] and pin['type'] == 'PASSIVE']
        for fuse_pin in fuse_pins:
            for connector, connector_pin in connector_pins:
                candidates.add((ref + '.pin:' + fuse_pin, connector + '.pin:' + connector_pin))
    if len(candidates) != 1:
        raise ValueError('Fuse-entry rule requires one unique directly connected header pin pair: ' + ref)
    fuse_pin, connector_pin = next(iter(candidates))
    return {'fuse_pin': fuse_pin, 'connected_connector_pin': connector_pin}
