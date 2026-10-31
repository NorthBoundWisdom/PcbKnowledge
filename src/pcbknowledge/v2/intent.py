"""Cross-reference checks for the ADR-023 design-intent handoff."""
from __future__ import annotations
from .catalog import LEVELS, unique
from .footprints import footprint_name
from .pin_defaults import connection_check, validate_default_checks


def validate_intent(catalog, intent, *, bundle_commit):
    catalog.structure(intent, 'design-intent.schema.json')
    if intent['bundle_commit'] != bundle_commit:
        raise ValueError('Design intent does not match selected bundle commit')
    catalog._anchors(intent)
    components = unique(intent['components'], 'ref', 'intent component ref')
    used = set(intent.get('dependencies', []))
    parts = {}
    for ref, component in components.items():
        part = catalog.get(component['part'], 'part')
        if component['package'] != part['package']:
            raise ValueError('Intent component package disagrees with selected part')
        if component['footprint'] != 'pcbknowledge:' + footprint_name(part['package']):
            raise ValueError('Footprint identity disagrees with selected package')
        parts[ref] = part
        used.update((part['id'], part['package']))
    nets = unique(intent['nets'], 'name', 'intent net name')
    connections = {}
    for name, net in nets.items():
        for endpoint in net['pins']:
            ref, number = (endpoint['ref'], endpoint['pin'])
            if ref not in parts or number not in {p['number'] for p in parts[ref]['pins']}:
                raise ValueError('Dangling design-intent pin')
            if (ref, number) in connections:
                raise ValueError('Intent pin connected more than once')
            connections[ref, number] = name
    from .single_supply import validate_projection as validate_single_supply
    if intent['status'] == 'EXPANDED':
        validate_single_supply(parts, connections, intent)
    from .bringup_contract import validate_bringup, bringup_sources
    validate_bringup(intent, catalog)
    used.update(bringup_sources(intent.get('bringup', {})))
    from .gpio import validate_configurations, validate_configured_drivers
    validate_configurations(catalog, parts, intent.get('pin_configurations', []))
    validate_configured_drivers(parts, intent.get('pin_configurations', []), connections)
    from .power_sinks import validate_loads
    validate_loads(catalog, parts, intent['nets'], intent.get('external_loads', []), used)
    _validate_bom(intent, parts)
    for mount in intent['mechanical']['mounting']:
        if mount['ref'] not in components or 'mechanical.mounting-hole' not in parts[mount['ref']]['roles']:
            raise ValueError('Dangling mounting component')
    if not set(intent['mechanical']['edge_interfaces']) <= set(components):
        raise ValueError('Dangling edge-interface component')
    from .kelvin_contract import validate_kelvin
    for constraint in intent['layout']:
        validate_kelvin(constraint, {r: [p] for r, p in parts.items()}, connections)
        for branch in constraint.get('branches', []):
            if (branch['evidence'] not in intent['evidence']
                    or branch['evidence']['source'] not in intent['dependencies']):
                raise ValueError('Kelvin branch source is absent from intent evidence closure')
        catalog._layout_references(constraint, {r: [p] for r, p in parts.items()}, set(nets))
    from .conductor_keepouts import validate_projection
    if intent['status'] == 'EXPANDED' or any(c['kind'] == 'CONDUCTOR_KEEPOUT' for c in intent['layout']):
        validate_projection(intent, catalog)
    fab_id = intent['fab_profile']
    if isinstance(fab_id, str):
        fab = catalog.get(fab_id, 'fab_profile')
        used.add(fab_id)
        from .reference_paths import validate_reference_paths
        validate_reference_paths(intent['layout'], set(nets), fab)
        from .assembly import validate_assembly
        validate_assembly(catalog, intent)
        if intent['manufacturing']['layers'] != fab['layer_count']:
            raise ValueError('Manufacturing layer count differs from fab profile')
        if intent['manufacturing']['assembly_side'] != fab['assembly_side']:
            raise ValueError('Manufacturing assembly side differs from fab profile')
    if intent['status'] == 'EXPANDED':
        from .edge_constraints import validate_edge_constraints
        validate_edge_constraints(intent['layout'], intent['mechanical']['outline_envelope'])
        if not isinstance(fab_id, str):
            raise ValueError('Expanded intent requires a resolved fab profile')
        requested = intent['manufacturing']['thickness'].get('value')
        allowed = fab['thickness']
        low = allowed.get('value', allowed.get('min'))
        high = allowed.get('value', allowed.get('max'))
        if requested is None or low is None or high is None or (not low <= requested <= high):
            raise ValueError('Manufacturing thickness differs from fab profile')
    _validate_checks_and_closure(catalog, intent, parts, used)
    return intent


def electrical_checks(parts, nets, external_loads=()):
    """Recompute electrical topology checks, never trust supplied PASS labels."""
    connections = {(p['ref'], p['pin']): net['name'] for net in nets for p in net['pins']}
    checks = []

    def add(identity, passed, reason):
        checks.append({'id': identity, 'result': 'PASS' if passed else 'FAIL', 'reason': reason})

    def component_nets(ref):
        return {connections.get((ref, p['number'])) for p in parts[ref]['pins']} - {None}
    for net in nets:
        drivers = set()
        for endpoint in net['pins']:
            part = parts.get(endpoint['ref'])
            if not part:
                continue
            pin = next((p for p in part['pins'] if p['number'] == endpoint['pin']), None)
            if pin and pin['type'] in ('OUTPUT', 'POWER_OUT'):
                drivers.add((endpoint['ref'], pin.get('same_net_as', pin['number'])))
        if drivers:
            add('drivers:' + net['name'], len(drivers) <= 1, 'No conflicting output drivers on one net')
    for ref, part in sorted(parts.items()):
        ground = {connections.get((ref, p['number'])) for p in part['pins'] if p['type'] == 'GROUND'} - {None}
        for pin in part['pins']:
            key = (ref, pin['number'])
            if pin['type'] in ('POWER_IN', 'GROUND', 'INPUT'):
                checks.append(connection_check(ref, pin, key in connections))
            if pin.get('same_net_as'):
                add(
                    'alias:' + ref + ':' + pin['number'],
                    key in connections and connections[key] == connections.get((ref, pin['same_net_as'])),
                    'Aliased physical terminals share a net',
                )
            _check_pin_support(ref, part, pin, key, ground, parts, connections, component_nets, add)
        if 'led' in part['roles']:
            resistors = [r for r, p in parts.items() if 'resistor' in p['roles']]
            own = component_nets(ref)
            series_nodes = {
                net['name'] for net in nets
                if len(net['pins']) == 2 and any(p['ref'] == ref for p in net['pins'])
            }
            passed = any((series_nodes & component_nets(r) and len(component_nets(r)) == 2 for r in resistors))
            add('led_resistor:' + ref, passed, 'LED has a connected current-limiting resistor')
    from .power_sinks import sink_checks
    checks.extend(sink_checks(parts, nets, external_loads))
    return checks


def _validate_bom(intent, parts):
    bom = {}
    for item in intent['bom']:
        if item['part'] in bom or item['quantity'] != len(item['refs']) or len(set(item['refs'])) != len(item['refs']):
            raise ValueError('Invalid BOM quantity or duplicate part')
        bom[item['part']] = set(item['refs'])
    expected = {}
    for ref, part in parts.items():
        expected.setdefault(part['id'], set()).add(ref)
    if bom != expected:
        raise ValueError('BOM does not cover the selected components exactly')


def _validate_checks_and_closure(catalog, intent, parts, used):
    checks = unique(intent['checks'], 'id', 'intent check id')
    validate_default_checks(parts, intent['nets'], checks)
    if intent['status'] == 'EXPANDED':

        def concrete(value):
            if isinstance(value, dict):
                if value.get('status') == 'UNKNOWN':
                    raise ValueError('Expanded intent uses UNKNOWN')
                for child in value.values():
                    concrete(child)
            elif isinstance(value, list):
                for child in value:
                    concrete(child)
        concrete(intent)
        actual_checks = electrical_checks(parts, intent['nets'], intent.get('external_loads', []))
        for actual in actual_checks:
            if actual['result'] != 'PASS':
                raise ValueError('Electrical check failed: ' + actual['id'])
        if (any(checks.get(actual['id'], {}).get('result') != 'PASS' for actual in actual_checks)
                or any(check['result'] != 'PASS' for check in checks.values())):
            raise ValueError('Electrical checks are incomplete or failed')

    def closure(identity):
        record = catalog.get(identity)
        if identity in visited:
            return
        visited.add(identity)
        if intent['status'] == 'EXPANDED':
            concrete(record)

        def anchors(value):
            if isinstance(value, dict):
                if 'source' in value and 'page' in value:
                    closure(value['source'])
                for child in value.values():
                    anchors(child)
            elif isinstance(value, list):
                for child in value:
                    anchors(child)
        anchors(record)
        for override in record.get('overrides', []):
            closure(override['rule'])
    used.update((anchor['source'] for anchor in intent['evidence']))
    visited = set()
    for identity in used:
        closure(identity)
    weakest = min((catalog.get(i)['verification'] for i in visited), key=LEVELS.index, default='DRAFT')
    if intent['verification'] != weakest:
        raise ValueError(f'Intent verification must be computed from all dependencies: {weakest}')


def _check_pin_support(ref, part, pin, key, ground, parts, connections, component_nets, add):
    if pin['type'] == 'POWER_IN' and part.get('single_supply_return'):
        from .single_supply import binding
        descriptor = part['single_supply_return']
        if pin['number'] in (descriptor['positive_pin'], descriptor['negative_pin']):
            try:
                binding(parts, connections, ref)
                passed = True
            except ValueError:
                passed = False
            add('decoupling:' + ref + ':' + pin['number'], passed,
                'Single-supply pair has sourced nominal bypass; negative terminal serves as return')
            return
    if pin['type'] == 'POWER_IN':
        from .bootstrap import decoupling
        try:
            bootstrap = decoupling(parts, connections, ref, pin['number'])
        except ValueError:
            bootstrap = False
        if bootstrap is not None:
            add('decoupling:' + ref + ':' + pin['number'], bootstrap,
                'Floating bootstrap pin has its sourced capacitor to the exact switch reference')
            return
        rail = connections.get(key)
        caps = [c for c, p in parts.items() if 'capacitor.ceramic' in p['roles']]
        passed = rail is not None and rail not in ground and any(
            rail in component_nets(c) and ground & component_nets(c) and len(component_nets(c)) == 2
            for c in caps
        )
        add('decoupling:' + ref + ':' + pin['number'], passed, 'Power pin has a capacitor to its local ground')
    if pin['type'] == 'OPEN_DRAIN' or pin.get('name') in ('SDA', 'SCL'):
        signal = connections.get(key)
        rails = {connections.get((ref, p['number'])) for p in part['pins'] if p['type'] == 'POWER_IN'} - {None, signal}
        # A current-sense shunt does not create a different logic domain.
        changed = True
        while changed:
            before = set(rails)
            for resistor_ref, resistor in parts.items():
                resistance = resistor.get('parameters', {}).get('resistance', {})
                high = resistance.get('max', resistance.get('value'))
                if ('resistor' in resistor['roles'] and resistance.get('unit') == 'ohm'
                        and isinstance(high, (int, float)) and high <= 1
                        and component_nets(resistor_ref) & rails):
                    rails.update(component_nets(resistor_ref))
            changed = before != rails
        resistors = [r for r, p in parts.items() if 'resistor' in p['roles']]
        passed = signal is not None and any(
            signal in component_nets(r) and rails & component_nets(r) and len(component_nets(r)) == 2
            for r in resistors
        )
        add('pullup:' + ref + ':' + pin['number'], passed, 'Open-drain signal has a resistive pull-up to a power rail')
