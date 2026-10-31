"""Bind layout rule templates to resolved components and electrical nets."""
from copy import deepcopy

from .reference_paths import NET_FIELDS


def _decoupling_options(catalog, parts, connections, ref, part, pin, bindings, assigned_caps):
    def component_nets(component):
        return {connections.get((component, p['number'])) for p in parts[component]['pins']} - {None}
    grounds = {
        connections.get((ref, p['number'])) for p in part['pins']
        if p['type'] == 'GROUND'
    } - {None}
    from .bootstrap import capacitor_binding, validate_part
    descriptors = validate_part(part, catalog.evidence) if part.get('bootstrap_supplies') else []
    descriptor = next((d for d in descriptors
                       if pin and d['bootstrap_pin'] == pin['number']), None)
    if descriptor is not None:
        chosen, _, _ = capacitor_binding(parts, connections, ref, descriptor, catalog.evidence)
        candidates = [chosen]
    else:
        candidates = [c for c,p in sorted(parts.items())
            if 'capacitor.ceramic' in p['roles'] and bindings.get('net') in component_nets(c)
            and grounds & component_nets(c)]
    # Prefer each instance's own capacitor, then an unused one.
    # Geometry is not available yet; the resulting PLACE_NEAR
    # constraint makes this explicit for the downstream placer.
    prefix = ref.rsplit('_',1)[0] + '_'
    candidates.sort(key=lambda c:(not c.startswith(prefix), c in assigned_caps, c))
    options = []
    if candidates:
        chosen = candidates[0]
        assigned_caps.add(chosen)
        options = [{**bindings,'decoupling_capacitor':chosen}]
    return options


def apply_rules(catalog, parts, nets, block_layout=()):
    connections = {(p['ref'],p['pin']):net['name'] for net in nets for p in net['pins']}
    constraints, used = [], set()
    for rule in catalog.search('rule'):
        applies = rule['applies_to']
        assigned_caps = set()
        for ref, part in sorted(parts.items()):
            if 'part' in applies and applies['part'] != part['id']:
                continue
            if 'role' in applies and applies['role'] not in part['roles']:
                continue
            pins = [p for p in part['pins'] if p['type']==applies['pin_type']] if 'pin_type' in applies else [None]
            for pin in pins:
                bindings = {'component':ref}
                if pin:
                    key = ref,pin['number']
                    if key not in connections:
                        continue
                    bindings.update(power_pin=ref+'.pin:'+pin['number'], net=connections[key])
                for raw in rule['layout']:
                    overridden = any(override['rule'] == rule['id'] for override in part.get('overrides', []))
                    if overridden:
                        references = {ref}
                        if pin:
                            references.update((ref+'.pin:'+pin['number'], ref+'.pin:'+pin['name']))
                        def replacement(constraint):
                            values = []
                            for field in ('subject','target','subjects','path'):
                                value = constraint.get(field, [])
                                values.extend([value] if isinstance(value,str) else value)
                            touches_net = 'net' in bindings and constraint.get('net') == bindings['net']
                            return constraint['kind'] == raw['kind'] and (bool(references & set(values)) or touches_net)
                        if not any(replacement(constraint) for constraint in block_layout):
                            raise ValueError('Rule override has no block-provided replacement: ' + ref)
                        used.add(rule['id'])
                        continue
                    if raw.get('subject') == 'fuse_pin' or raw.get('target') == 'connected_connector_pin':
                        from .fuse_rules import fuse_entry_bindings
                        bindings.update(fuse_entry_bindings(ref, parts, nets))
                    options = [bindings]
                    if raw.get('subject') == 'decoupling_capacitor':
                        options = _decoupling_options(
                            catalog, parts, connections, ref, part, pin, bindings, assigned_caps)
                    for mapping in options:
                        constraint = deepcopy(raw)
                        for key in ('subject', 'target', 'subjects', 'path', *NET_FIELDS):
                            if key not in constraint:
                                continue
                            value = constraint[key]
                            def resolve(token):
                                if token not in mapping:
                                    raise ValueError('Unbound rule template token: ' + token)
                                return mapping[token]
                            constraint[key] = resolve(value) if isinstance(value,str) else [resolve(v) for v in value]
                        if constraint not in constraints:
                            constraints.append(constraint)
                        used.add(rule['id'])
    return constraints, used
