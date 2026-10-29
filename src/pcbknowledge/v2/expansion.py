"""Pure block-graph expansion from one validated catalog snapshot."""
from __future__ import annotations

from copy import deepcopy
import hashlib

from pcbknowledge.serialization import canonical_json
from .calculators import evaluate_check
from .catalog import LEVELS, unique
from .footprints import footprint_name
from .intent import validate_intent


def unknown(reason):
    return {'status': 'UNKNOWN', 'reason': reason, 'blocks': ['Q10']}


def dependency_closure(catalog, identities):
    visited = set()
    def visit(identity):
        if identity in visited:
            return
        record = catalog.get(identity)
        visited.add(identity)
        if identity.startswith('part:'):
            visit(record['package'])
        def walk(value):
            if isinstance(value, dict):
                if 'source' in value and 'page' in value:
                    visit(value['source'])
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(record)
        for override in record.get('overrides', []):
            visit(override['rule'])
    for identity in sorted(identities):
        visit(identity)
    return visited


def expand_bundle(path, graph):
    from .bundle import Bundle
    with Bundle(path) as bundle:
        if graph.get('brief') not in bundle.briefs:
            raise ValueError('Graph brief is absent from selected bundle')
        return expand(bundle.catalog, graph, bundle.briefs[graph['brief']], bundle_commit=bundle.commit)


def expand(catalog, graph, brief, *, bundle_commit):
    """Resolve components, unite port nets and emit typed refusals on unsafe inputs."""
    mechanical = brief['mechanical']
    manufacturing = brief['manufacturing']
    intent = {'schema': 'pcbknowledge.design_intent.v2', 'id': (str(graph.get('id', 'invalid')) + '-expanded')[:256],
              'brief_id': brief['id'], 'bundle_commit': bundle_commit,
              'block_graph_sha256': hashlib.sha256(canonical_json(graph).encode()).hexdigest(),
              'status': 'REFUSED', 'components': [], 'nets': [], 'bom': [], 'layout': [],
              'checks': [], 'verification': 'DRAFT', 'refusals': [], 'evidence': [],
              'dependencies': [], 'fab_profile': manufacturing['profile'],
              'mechanical': {'outline_envelope': {'shape': 'RECTANGLE',
                  'max_length': deepcopy(mechanical['length']), 'max_width': deepcopy(mechanical['width'])},
                  'height_limit': deepcopy(mechanical['height']), 'mounting': [], 'edge_interfaces': []},
              'manufacturing': {'layers': manufacturing['layers'],
                  'thickness': deepcopy(manufacturing['thickness']),
                  'copper_requirement': 'ONE_OZ_NOMINAL' if manufacturing['copper'].startswith('1 oz copper') else unknown('Copper requirement is not supported'),
                  'assembly_side': 'TOP' if manufacturing['assembly'] == 'Single-side assembly' else unknown('Assembly side is not supported')}}
    def refuse(code, path, reason, queries=('Q10',)):
        item = {'code': code, 'path': path, 'reason': str(reason)[:256], 'queries': list(queries)}
        if item not in intent['refusals']:
            intent['refusals'].append(item)
    used = set()
    parts = {}
    blocks = {}
    local_parts = {}
    parent = {}
    pin_nodes = {}
    port_nodes = {}
    labels = {}
    def find(node):
        parent.setdefault(node, node)
        if parent[node] != node:
            parent[node] = find(parent[node])
        return parent[node]
    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a,b)] = min(a,b)
    try:
        catalog.structure(graph, 'block-graph.schema.json')
        catalog.structure(brief, 'design-brief.schema.json')
        if graph['brief'] != brief['id']:
            raise ValueError('Graph and brief identities differ')
        instances = unique(graph['instances'], 'id', 'graph instance')
        requirements = {item['id'] for group in ('functions','interfaces','constraints') for item in brief[group]}
        requirements.update(item['id'] for item in brief['mechanical']['mounting'])
        declared_requirements = set(graph['requirements'])
        for instance in instances.values():
            declared_requirements.update(instance['requirements'])
        if declared_requirements != requirements:
            raise ValueError('Graph requirement coverage differs from brief')
        for function in brief['functions']:
            count = sum(function['id'] in instance['requirements'] for instance in instances.values())
            if count != function['count']:
                raise ValueError('Graph function count differs from brief: ' + function['id'])
        unique(graph['connections'], 'net', 'graph net')
        for group in ('sources','rails'):
            for supply in brief['power'][group]:
                function_id = supply.get('function')
                consumers = [instance for instance in instances.values() if function_id in instance['requirements']]
                if not function_id or not consumers:
                    refuse('UNKNOWN_INPUT', 'power.'+group+'.'+supply['id'], 'Power requirement has no function binding')
                    continue
                for instance in consumers:
                    for parameter, requirement in (('output_voltage','voltage'),('output_current','current_budget')):
                        expected = supply[requirement]
                        supplied = instance['parameters'].get(parameter, {})
                        keys = ('value','min','typ','max','unit')
                        if {k:expected[k] for k in keys if k in expected} != {k:supplied[k] for k in keys if k in supplied}:
                            refuse('CHECK_FAILED', instance['id']+'.parameters.'+parameter,
                                   'Block power output differs from brief '+requirement)
        for iid, instance in sorted(instances.items()):
            try:
                block = catalog.get(instance['block'], 'block')
            except ValueError as error:
                refuse('MISSING_RECORD', iid + '.block', error, ('Q6',))
                continue
            blocks[iid] = block
            used.add(block['id'])
            for function in brief['functions']:
                if function['id'] not in instance['requirements']:
                    continue
                if not function.get('category'):
                    refuse('UNKNOWN_INPUT', 'functions.'+function['id'], 'Function category is not specified')
                elif function['category'] != block['category']:
                    refuse('CHECK_FAILED', iid+'.requirements', 'Block category does not satisfy the claimed function')
                for name, expected in function['parameters'].items():
                    supplied = instance['parameters'].get(name, {})
                    keys = ('value','min','typ','max','unit')
                    if {k:expected[k] for k in keys if k in expected} != {k:supplied[k] for k in keys if k in supplied}:
                        refuse('CHECK_FAILED', iid+'.parameters.'+name, 'Block input differs from brief function requirement')
            ports = {p['name']: p['kind'] for p in block['ports']}
            declared = {p['name']: p['type'] for p in instance['ports']}
            if len(declared) != len(instance['ports']) or ports != declared:
                raise ValueError('Graph ports differ from block contract: ' + iid)
            if set(instance['parameters']) - set(block['parameters']):
                raise ValueError('Graph supplies undeclared block parameter: ' + iid)
            for name, parameter in block['parameters'].items():
                if parameter['required'] and name not in instance['parameters']:
                    refuse('UNKNOWN_INPUT', iid + '.parameters.' + name, 'Required parameter missing')
                if name in instance['parameters']:
                    catalog.vocabulary.quantity(instance['parameters'][name], parameter['quantity'])
                if 'fixed' in parameter and name in instance['parameters']:
                    numeric = lambda value: {key:value[key] for key in ('value','min','typ','max','unit') if key in value}
                    if numeric(parameter['fixed']) != numeric(instance['parameters'][name]):
                        refuse('CHECK_FAILED', iid + '.parameters.' + name, 'Parameter differs from fixed block operating requirement')
            local_parts[iid] = {}
            for component in sorted(block['components'], key=lambda c: c['ref']):
                try:
                    candidates = catalog._candidates(component['select'])
                except ValueError as error:
                    refuse('UNSATISFIED_SELECTION', iid + '.' + component['ref'], error, ('Q1',))
                    continue
                if not candidates:
                    refuse('UNSATISFIED_SELECTION', iid + '.' + component['ref'], 'No candidate matches the requested selection', ('Q1',))
                    continue
                part = sorted(candidates, key=lambda p: (-LEVELS.index(p['verification']), p['id']))[0]
                ref = iid + '_' + component['ref']
                if ref in parts:
                    raise ValueError('Qualified component reference collision: ' + ref)
                parts[ref] = part
                local_parts[iid][component['ref']] = part
                used.update((part['id'], part['package']))
                intent['components'].append({'ref': ref, 'part': part['id'], 'package': part['package'],
                    'footprint': 'pcbknowledge:' + footprint_name(part['package'])})
                if 'mechanical.mounting-hole' in part['roles']:
                    intent['mechanical']['mounting'].append({'ref': ref, 'fastener': 'M3'})
            for net in block['nets']:
                node = iid + ':' + net['name']
                find(node)
                for endpoint in net['connect']:
                    if endpoint.startswith('port:'):
                        port_nodes[iid,endpoint[5:]] = node
                    else:
                        ref, _, pin = endpoint.partition('.pin:')
                        part = local_parts[iid].get(ref)
                        if not part:
                            continue
                        matches = [p for p in part['pins'] if p['name'] == pin or p['number'] == pin]
                        for match in matches:
                            key = (iid + '_' + ref, match['number'])
                            if key in pin_nodes and pin_nodes[key] != node:
                                raise ValueError('Physical pin assigned to multiple nets')
                            pin_nodes[key] = node
            for index, check in enumerate(block['checks']):
                result = evaluate_check(check, instance['parameters'], local_parts[iid])
                passed = result['result'] == 'PASS'
                intent['checks'].append({'id': iid + ':calculator:' + str(index),
                    'result': 'PASS' if passed else 'FAIL', 'reason': result.get('reason', check['calculator'])[:256]})
                if not passed:
                    refuse('CHECK_FAILED', iid + '.checks.' + str(index), result.get('reason', check['calculator']))
        seen_ports = set()
        for connection in graph['connections']:
            nodes = []
            for endpoint in connection['endpoints']:
                key = endpoint['instance'], endpoint['port']
                if key in seen_ports:
                    raise ValueError('Graph port appears in multiple connections')
                seen_ports.add(key)
                if key not in port_nodes:
                    raise ValueError('Unknown graph port: ' + '.'.join(key))
                nodes.append(port_nodes[key])
            for node in nodes[1:]:
                union(nodes[0], node)
            labels.setdefault(nodes[0], []).append(connection['net'])
        if set(port_nodes) != seen_ports:
            refuse('UNCONNECTED_PIN', 'connections', 'Not all block ports are connected')
        names = {}
        for node, values in labels.items():
            names.setdefault(find(node), set()).update(values)
        if any(len(values) > 1 for values in names.values()):
            raise ValueError('Different graph nets are shorted through a block')
        resolved = {node: next(iter(names[find(node)])) if find(node) in names
                    else find(node).replace(':','_').upper() for node in parent}
        named_roots = {}
        for node, name in resolved.items():
            if name in named_roots and named_roots[name] != find(node):
                raise ValueError('Qualified net name collision: ' + name)
            named_roots[name] = find(node)
        nets = {}
        for (ref, pin), node in sorted(pin_nodes.items()):
            nets.setdefault(resolved[node], []).append({'ref':ref,'pin':pin})
        kinds = {}
        for (iid, port), node in port_nodes.items():
            kind = next(p['kind'] for p in blocks[iid]['ports'] if p['name'] == port)
            kinds.setdefault(resolved[node], set()).add(kind)
        for name, pins in sorted(nets.items()):
            types = kinds.get(name, set())
            for endpoint in pins:
                types.add(next(p['type'] for p in parts[endpoint['ref']]['pins'] if p['number'] == endpoint['pin']))
            power = bool(types & {'POWER_IN','POWER_OUT'})
            ground = 'GROUND' in types
            if power and ground:
                refuse('CHECK_FAILED', 'nets.' + name, 'Power and ground are shorted')
            intent['nets'].append({'name':name, 'pins':pins,
                                   'class':'GROUND' if ground else 'POWER' if power else 'SIGNAL'})
        # A connected capacitor is not a source: follow declared power paths
        # from actual power-input blocks through fully supplied downstream blocks.
        powered = set()
        source_grounds = set()
        for iid, block in blocks.items():
            if block['category'] == 'power.input':
                powered.update(resolved[port_nodes[iid,p['name']]] for p in block['ports'] if p['kind']=='POWER_OUT')
                source_grounds.update(resolved[port_nodes[iid,p['name']]] for p in block['ports'] if p['kind']=='GROUND')
        changed = True
        while changed:
            before = set(powered)
            for iid, block in blocks.items():
                inputs = {resolved[port_nodes[iid,p['name']]] for p in block['ports'] if p['kind']=='POWER_IN'}
                if inputs and inputs <= powered:
                    powered.update(resolved[port_nodes[iid,p['name']]] for p in block['ports'] if p['kind']=='POWER_OUT')
            for ref, part in parts.items():
                resistance = part.get('parameters', {}).get('resistance', {})
                high = resistance.get('max', resistance.get('value'))
                # Resistors and fuses conduct DC; capacitors do not. This is
                # reachability, while voltage/current limits belong to block checks.
                if ('resistor' in part['roles'] and resistance.get('unit') == 'ohm'
                        and isinstance(high, (int,float)) and high >= 0) or 'protection.fuse' in part['roles']:
                    connected = {resolved[pin_nodes[ref,p['number']]] for p in part['pins'] if (ref,p['number']) in pin_nodes}
                    if connected & powered:
                        powered.update(connected)
            changed = before != powered
        for ref, part in parts.items():
            for pin in part['pins']:
                if pin['type'] not in ('POWER_IN','GROUND'):
                    continue
                node = pin_nodes.get((ref,pin['number']))
                net = resolved.get(node)
                allowed = powered if pin['type']=='POWER_IN' else source_grounds
                passed = net in allowed
                identity = 'source:'+ref+':'+pin['number']
                intent['checks'].append({'id':identity, 'result':'PASS' if passed else 'FAIL',
                                         'reason':'Pin reaches a declared board power source'})
                if not passed:
                    refuse('CHECK_FAILED', identity, 'Power or ground pin has no board-source path')
        for iid, block in sorted(blocks.items()):
            for raw in block['layout']:
                constraint = deepcopy(raw)
                for key in ('subject','target','subjects','path'):
                    if key in constraint:
                        value = constraint[key]
                        constraint[key] = iid + '_' + value if isinstance(value,str) else [iid+'_'+v for v in value]
                for key in ('net','sense_nets'):
                    if key in constraint:
                        value = constraint[key]
                        constraint[key] = resolved[iid+':'+value] if isinstance(value,str) else [resolved[iid+':'+v] for v in value]
                intent['layout'].append(constraint)
                if constraint['kind'] == 'EDGE_PLACEMENT':
                    intent['mechanical']['edge_interfaces'].append(constraint['subject'].split('.pin:')[0])
        from .rules import apply_rules
        constraints, rules_used = apply_rules(catalog, parts, intent['nets'], intent['layout'])
        used.update(rules_used)
        for constraint in constraints:
            if constraint not in intent['layout']:
                intent['layout'].append(constraint)
            if constraint['kind'] == 'EDGE_PLACEMENT':
                intent['mechanical']['edge_interfaces'].append(constraint['subject'].split('.pin:')[0])
        intent['mechanical']['edge_interfaces'] = sorted(set(intent['mechanical']['edge_interfaces']))
        bom = {}
        for ref, part in sorted(parts.items()):
            bom.setdefault(part['id'], []).append(ref)
        intent['bom'] = [{'part': part, 'refs': refs, 'quantity': len(refs)} for part,refs in sorted(bom.items())]
        if isinstance(intent['fab_profile'], str):
            used.add(intent['fab_profile'])
        else:
            refuse('UNKNOWN_INPUT', 'fab_profile', 'Fab profile is unresolved', ('Q9',))
    except (ValueError, KeyError, TypeError) as error:
        refuse('INVALID_REFERENCE', 'graph', error)
    # Dependency closure is explicit, including the block and rule authorities.
    try:
        dependencies = dependency_closure(catalog, used)
        intent['dependencies'] = sorted(dependencies)
        intent['verification'] = min((catalog.get(i)['verification'] for i in dependencies), key=LEVELS.index, default='DRAFT')
        def inspect(value, path):
            if isinstance(value, dict):
                if value.get('status') == 'UNKNOWN':
                    refuse('UNKNOWN_INPUT', path, value['reason'], value['blocks'])
                if 'source' in value and 'page' in value:
                    anchor = {'source':value['source'],'page':value['page']}
                    if anchor not in intent['evidence']:
                        intent['evidence'].append(anchor)
                for key, child in value.items():
                    inspect(child, path + '.' + key)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    inspect(child, path + '.' + str(index))
        for identity in sorted(dependencies):
            record = catalog.get(identity)
            inspect(record, identity)
            if record['verification'] == 'DRAFT':
                refuse('UNVERIFIED_RECORD', identity, 'Dependency is DRAFT')
        inspect(graph, 'graph')
        inspect(brief, 'brief')
        inspect(intent['manufacturing'], 'manufacturing')
    except (ValueError, KeyError) as error:
        refuse('MISSING_RECORD', 'dependencies', error)
    from .intent import electrical_checks
    for check in electrical_checks(parts, intent['nets']):
        intent['checks'].append(check)
        if check['result'] != 'PASS':
            refuse('CHECK_FAILED', check['id'], check['reason'])
    intent['evidence'].sort(key=lambda a:(a['source'],a['page']))
    intent['checks'].sort(key=lambda c:c['id'])
    if not intent['refusals']:
        intent['status'] = 'EXPANDED'
        try:
            validate_intent(catalog, intent, bundle_commit=bundle_commit)
        except ValueError as error:
            intent['status'] = 'REFUSED'
            refuse('CHECK_FAILED', 'intent', error)
    catalog.structure(intent, 'design-intent.schema.json')
    return intent


def validate_expansion(bundle, intent, graph):
    """Replay before consuming external intent JSON; PASS claims are not authority."""
    if graph.get('brief') not in bundle.briefs:
        raise ValueError('Graph brief is absent from bundle')
    expected = expand(bundle.catalog, graph, bundle.briefs[graph['brief']], bundle_commit=bundle.commit)
    if intent != expected:
        raise ValueError('Design intent differs from deterministic bundle/graph expansion')
    if intent['status'] != 'EXPANDED':
        raise ValueError('Design intent is refused')
    return intent
