"""Pure block-graph expansion from one validated catalog snapshot."""
from __future__ import annotations

from copy import deepcopy
import hashlib

from pcbknowledge.serialization import canonical_json
from .calculators import evaluate_check
from .catalog import LEVELS, unique, selected_candidate
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


def _numeric(value):
    return {key: value[key] for key in ('value', 'min', 'typ', 'max', 'unit') if key in value}


def _initial_intent(graph, brief, bundle_commit):
    mechanical = brief['mechanical']
    manufacturing = brief['manufacturing']
    return {'schema': 'pcbknowledge.design_intent.v2', 'id': (str(graph.get('id', 'invalid')) + '-expanded')[:256],
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
                  'copper_requirement': {'ONE_OZ': 'ONE_OZ_NOMINAL'}[manufacturing['copper']],
                  'assembly_side': {'SINGLE_SIDE_TOP': 'TOP'}[manufacturing['assembly']]}}


class _Expansion:
    """Mutable state for one pure expansion, partitioned into ordered phases."""

    def __init__(self, catalog, graph, brief, bundle_commit):
        self.catalog = catalog
        self.graph = graph
        self.brief = brief
        self.bundle_commit = bundle_commit
        self.intent = _initial_intent(graph, brief, bundle_commit)
        self.used = set()
        self.parts = {}
        self.blocks = {}
        self.local_parts = {}
        self.parent = {}
        self.pin_nodes = {}
        self.port_nodes = {}
        self.labels = {}

    def refuse(self, code, path, reason, queries=('Q10',)):
        item = {'code': code, 'path': path, 'reason': str(reason)[:256], 'queries': list(queries)}
        if item not in self.intent['refusals']:
            self.intent['refusals'].append(item)

    def find(self, node):
        self.parent.setdefault(node, node)
        if self.parent[node] != node:
            self.parent[node] = self.find(self.parent[node])
        return self.parent[node]

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.parent[max(a, b)] = min(a, b)

    def validate_graph(self):
        self.catalog.structure(self.graph, 'block-graph.schema.json')
        self.catalog.structure(self.brief, 'design-brief.schema.json')
        if self.graph['brief'] != self.brief['id']:
            raise ValueError('Graph and brief identities differ')
        self.instances = unique(self.graph['instances'], 'id', 'graph instance')
        requirements = {item['id'] for group in ('functions','interfaces','constraints') for item in self.brief[group]}
        requirements.update(item['id'] for item in self.brief['mechanical']['mounting'])
        declared_requirements = set(self.graph['requirements'])
        for instance in self.instances.values():
            declared_requirements.update(instance['requirements'])
        if declared_requirements != requirements:
            raise ValueError('Graph requirement coverage differs from brief')
        for function in self.brief['functions']:
            count = sum(function['id'] in instance['requirements'] for instance in self.instances.values())
            if count != function['count']:
                raise ValueError('Graph function count differs from brief: ' + function['id'])
        unique(self.graph['connections'], 'net', 'graph net')
        from .electrical_bindings import validate_bindings
        validate_bindings(self.brief)
        from .parameter_bindings import validate_bindings as validate_parameters
        validate_parameters(self.brief, self.catalog)

    def check_power_requirements(self):
        for group in ('sources','rails'):
            for supply in self.brief['power'][group]:
                function_id = supply.get('function')
                consumers = [
                    instance for instance in self.instances.values() if function_id in instance['requirements']
                ]
                if not function_id or not consumers:
                    self.refuse(
                        'UNKNOWN_INPUT', 'power.' + group + '.' + supply['id'],
                        'Power requirement has no function binding'
                    )
                    continue
                for instance in consumers:
                    for parameter, requirement in (('output_voltage','voltage'),('output_current','current_budget')):
                        expected = supply[requirement]
                        supplied = instance['parameters'].get(parameter, {})
                        if _numeric(expected) != _numeric(supplied):
                            self.refuse('CHECK_FAILED', instance['id']+'.parameters.'+parameter,
                                   'Block power output differs from brief '+requirement)

    def resolve_instances(self):
        for iid, instance in sorted(self.instances.items()):
            try:
                block = self.catalog.get(instance['block'], 'block')
            except ValueError as error:
                self.refuse('MISSING_RECORD', iid + '.block', error, ('Q6',))
                continue
            self.blocks[iid] = block
            self.used.add(block['id'])
            self.check_function_requirements(iid, instance, block)
            self.check_instance_inputs(iid, instance, block)
            self.resolve_components(iid, block)
            self.check_package_family(iid, instance)
            self.index_block_nets(iid, block)
            self.check_calculators(iid, instance, block)

    def check_function_requirements(self, iid, instance, block):
        for function in self.brief['functions']:
            if function['id'] not in instance['requirements']:
                continue
            if not function.get('category'):
                self.refuse('UNKNOWN_INPUT', 'functions.'+function['id'], 'Function category is not specified')
            elif function['category'] != block['category']:
                self.refuse('CHECK_FAILED', iid+'.requirements', 'Block category does not satisfy the claimed function')
            from .parameter_bindings import parameters_for
            for name, expected in parameters_for(self.brief, function).items():
                supplied = instance['parameters'].get(name, {})
                if _numeric(expected) != _numeric(supplied):
                    self.refuse(
                        'CHECK_FAILED', iid + '.parameters.' + name,
                        'Block input differs from brief function requirement'
                    )

    def check_instance_inputs(self, iid, instance, block):
        ports = {p['name']: p['kind'] for p in block['ports']}
        declared = {p['name']: p['type'] for p in instance['ports']}
        if len(declared) != len(instance['ports']) or ports != declared:
            raise ValueError('Graph ports differ from block contract: ' + iid)
        if set(instance['parameters']) - set(block['parameters']):
            raise ValueError('Graph supplies undeclared block parameter: ' + iid)
        for name, parameter in block['parameters'].items():
            if parameter['required'] and name not in instance['parameters']:
                self.refuse('UNKNOWN_INPUT', iid + '.parameters.' + name, 'Required parameter missing')
            if name in instance['parameters']:
                self.catalog.vocabulary.quantity(instance['parameters'][name], parameter['quantity'])
            if 'fixed' in parameter and name in instance['parameters']:
                if _numeric(parameter['fixed']) != _numeric(instance['parameters'][name]):
                    self.refuse(
                        'CHECK_FAILED', iid + '.parameters.' + name,
                        'Parameter differs from fixed block operating requirement'
                    )

    def resolve_components(self, iid, block):
        self.local_parts[iid] = {}
        for component in sorted(block['components'], key=lambda c: c['ref']):
            try:
                candidates = self.catalog._candidates(component['select'])
            except ValueError as error:
                self.refuse('UNSATISFIED_SELECTION', iid + '.' + component['ref'], error, ('Q1',))
                continue
            if not candidates:
                self.refuse(
                    'UNSATISFIED_SELECTION', iid + '.' + component['ref'],
                    'No candidate matches the requested selection', ('Q1',)
                )
                continue
            part = selected_candidate(candidates)
            ref = iid + '_' + component['ref']
            if ref in self.parts:
                raise ValueError('Qualified component reference collision: ' + ref)
            self.parts[ref] = part
            self.local_parts[iid][component['ref']] = part
            self.used.update((part['id'], part['package']))
            self.intent['components'].append({'ref': ref, 'part': part['id'], 'package': part['package'],
                'footprint': 'pcbknowledge:' + footprint_name(part['package'])})
            if 'mechanical.mounting-hole' in part['roles']:
                self.intent['mechanical']['mounting'].append({'ref': ref, 'fastener': 'M3'})

    def check_package_family(self, iid, instance):
        from .requirements import package_selection_matches
        for function in self.brief['functions']:
            if function['id'] not in instance['requirements']:
                continue
            selected = self.local_parts[iid].values()
            if not package_selection_matches(self.catalog, function, selected):
                self.refuse('UNSATISFIED_SELECTION', iid + '.requirements',
                            'Selected role component does not satisfy package family: ' + function['package_family'],
                            ('Q1',))

    def index_block_nets(self, iid, block):
        for net in block['nets']:
            node = iid + ':' + net['name']
            self.find(node)
            for endpoint in net['connect']:
                if endpoint.startswith('port:'):
                    self.port_nodes[iid,endpoint[5:]] = node
                else:
                    ref, _, pin = endpoint.partition('.pin:')
                    part = self.local_parts[iid].get(ref)
                    if not part:
                        continue
                    matches = [p for p in part['pins'] if p['name'] == pin or p['number'] == pin]
                    for match in matches:
                        key = (iid + '_' + ref, match['number'])
                        if key in self.pin_nodes and self.pin_nodes[key] != node:
                            raise ValueError('Physical pin assigned to multiple nets')
                        self.pin_nodes[key] = node

    def check_calculators(self, iid, instance, block):
        for index, check in enumerate(block['checks']):
            result = evaluate_check(check, instance['parameters'], self.local_parts[iid])
            passed = result['result'] == 'PASS'
            self.intent['checks'].append({'id': iid + ':calculator:' + str(index),
                'result': 'PASS' if passed else 'FAIL', 'reason': result.get('reason', check['calculator'])[:256]})
            if not passed:
                self.refuse('CHECK_FAILED', iid + '.checks.' + str(index), result.get('reason', check['calculator']))

    def unite_nets(self):
        seen_ports = set()
        for connection in self.graph['connections']:
            nodes = []
            for endpoint in connection['endpoints']:
                key = endpoint['instance'], endpoint['port']
                if key in seen_ports:
                    raise ValueError('Graph port appears in multiple connections')
                seen_ports.add(key)
                if key not in self.port_nodes:
                    raise ValueError('Unknown graph port: ' + '.'.join(key))
                nodes.append(self.port_nodes[key])
            for node in nodes[1:]:
                self.union(nodes[0], node)
            self.labels.setdefault(nodes[0], []).append(connection['net'])
        if set(self.port_nodes) != seen_ports:
            self.refuse('UNCONNECTED_PIN', 'connections', 'Not all block ports are connected')
        names = {}
        for node, values in self.labels.items():
            names.setdefault(self.find(node), set()).update(values)
        if any(len(values) > 1 for values in names.values()):
            raise ValueError('Different graph nets are shorted through a block')
        self.resolved = {node: next(iter(names[self.find(node)])) if self.find(node) in names
                    else self.find(node).replace(':','_').upper() for node in self.parent}
        named_roots = {}
        for node, name in self.resolved.items():
            if name in named_roots and named_roots[name] != self.find(node):
                raise ValueError('Qualified net name collision: ' + name)
            named_roots[name] = self.find(node)

    def assemble_nets(self):
        nets = {}
        for (ref, pin), node in sorted(self.pin_nodes.items()):
            nets.setdefault(self.resolved[node], []).append({'ref':ref,'pin':pin})
        kinds = {}
        for (iid, port), node in self.port_nodes.items():
            kind = next(p['kind'] for p in self.blocks[iid]['ports'] if p['name'] == port)
            kinds.setdefault(self.resolved[node], set()).add(kind)
        for name, pins in sorted(nets.items()):
            types = kinds.get(name, set())
            for endpoint in pins:
                from .single_supply import negative_pin
                part = self.parts[endpoint['ref']]
                pin = endpoint['pin']
                if not negative_pin(part, pin):
                    types.add(next(p['type'] for p in part['pins'] if p['number'] == pin))
            power = bool(types & {'POWER_IN','POWER_OUT','POWER_SINK'})
            ground = 'GROUND' in types
            if power and ground:
                self.refuse('CHECK_FAILED', 'nets.' + name, 'Power and ground are shorted')
            self.intent['nets'].append({'name':name, 'pins':pins,
                                   'class':'GROUND' if ground else 'POWER' if power else 'SIGNAL'})

    def port_nets(self, iid, block, kind):
        return (
            self.resolved[self.port_nodes[iid, port['name']]]
            for port in block['ports'] if port['kind'] == kind
        )

    def check_source_paths(self):
        # A connected capacitor is not a source: follow declared power paths
        # from actual power-input blocks through fully supplied downstream blocks.
        self.powered = set()
        self.source_grounds = set()
        for iid, block in self.blocks.items():
            if block['category'] == 'power.input':
                self.powered.update(self.port_nets(iid, block, 'POWER_OUT'))
                self.source_grounds.update(self.port_nets(iid, block, 'GROUND'))
        changed = True
        while changed:
            before = set(self.powered)
            for iid, block in self.blocks.items():
                inputs = set(self.port_nets(iid, block, 'POWER_IN'))
                if inputs and inputs <= self.powered:
                    self.powered.update(self.port_nets(iid, block, 'POWER_OUT'))
            for ref, part in self.parts.items():
                resistance = part.get('parameters', {}).get('resistance', {})
                high = resistance.get('max', resistance.get('value'))
                # Resistors and fuses conduct DC; capacitors do not. This is
                # reachability, while voltage/current limits belong to block checks.
                if ('resistor' in part['roles'] and resistance.get('unit') == 'ohm'
                        and isinstance(high, (int,float)) and high >= 0) or 'protection.fuse' in part['roles']:
                    connected = {
                        self.resolved[self.pin_nodes[ref, pin['number']]]
                        for pin in part['pins'] if (ref, pin['number']) in self.pin_nodes
                    }
                    if connected & self.powered:
                        self.powered.update(connected)
            changed = before != self.powered
        bootstrap_pins = set()
        if any(part.get('bootstrap_supplies') for part in self.parts.values()):
            from .bootstrap import qualify
            pin_nets = {key: self.resolved[node] for key, node in self.pin_nodes.items()}
            try:
                bootstrap_pins, receipts = qualify(
                    self.parts, pin_nets, self.powered, self.source_grounds, self.catalog.evidence)
                for receipt in receipts:
                    self.intent['checks'].append({
                        'id': 'bootstrap:' + receipt['component'] + ':' + receipt['pin'],
                        'result': 'PASS', 'reason': receipt['reason'] + '; topology only'})
            except ValueError as error:
                self.intent['checks'].append({'id': 'bootstrap:topology', 'result': 'FAIL',
                                              'reason': str(error)[:256]})
                self.refuse('CHECK_FAILED', 'bootstrap:topology', error)
        pin_nets = {key: self.resolved[node] for key, node in self.pin_nodes.items()}
        single_returns = set()
        if any(part.get('single_supply_return') for part in self.parts.values()):
            from .single_supply import qualify as qualify_single
            try:
                single_returns, receipts = qualify_single(
                    self.parts, pin_nets, self.powered, self.source_grounds, self.catalog.evidence)
                self.intent['single_supply_returns'] = receipts
            except ValueError as error:
                self.refuse('CHECK_FAILED', 'single_supply_return', error)
        for ref, part in self.parts.items():
            for pin in part['pins']:
                if pin['type'] not in ('POWER_IN','GROUND'):
                    continue
                node = self.pin_nodes.get((ref,pin['number']))
                net = self.resolved.get(node)
                allowed = self.powered if pin['type']=='POWER_IN' else self.source_grounds
                bootstrap = pin['type'] == 'POWER_IN' and (ref, pin['number']) in bootstrap_pins
                passed = net in allowed or bootstrap or (ref, pin['number']) in single_returns
                identity = 'source:'+ref+':'+pin['number']
                self.intent['checks'].append({'id':identity, 'result':'PASS' if passed else 'FAIL',
                                         'reason': ('Source-backed floating bootstrap has powered charger'
                                                   if bootstrap else 'Pin reaches a declared board power source')})
                if not passed:
                    self.refuse('CHECK_FAILED', identity, 'Power or ground pin has no board-source path')

    def apply_layout_rules(self):
        for iid, block in sorted(self.blocks.items()):
            for raw in block['layout']:
                constraint = deepcopy(raw)
                from .kelvin_contract import prefix_branches
                prefix_branches(constraint, iid)
                for key in ('subject','target','subjects','path'):
                    if key in constraint:
                        value = constraint[key]
                        constraint[key] = iid + '_' + value if isinstance(value,str) else [iid+'_'+v for v in value]
                for key in ('net','sense_nets','nets','guard_net','return_net'):
                    if key in constraint:
                        value = constraint[key]
                        constraint[key] = (
                            self.resolved[iid + ':' + value] if isinstance(value, str)
                            else [self.resolved[iid + ':' + v] for v in value]
                        )
                self.intent['layout'].append(constraint)
                if constraint['kind'] == 'EDGE_PLACEMENT':
                    self.intent['mechanical']['edge_interfaces'].append(constraint['subject'].split('.pin:')[0])
        from .conductor_keepouts import project_keepouts
        self.intent['layout'].extend(project_keepouts(self.intent['components'], self.catalog))
        from .rules import apply_rules
        constraints, rules_used = apply_rules(self.catalog, self.parts, self.intent['nets'], self.intent['layout'])
        self.used.update(rules_used)
        for constraint in constraints:
            if constraint not in self.intent['layout']:
                self.intent['layout'].append(constraint)
            if constraint['kind'] == 'EDGE_PLACEMENT':
                self.intent['mechanical']['edge_interfaces'].append(constraint['subject'].split('.pin:')[0])
        self.intent['mechanical']['edge_interfaces'] = sorted(set(self.intent['mechanical']['edge_interfaces']))

    def assemble_bom(self):
        bom = {}
        for ref, part in sorted(self.parts.items()):
            bom.setdefault(part['id'], []).append(ref)
        self.intent['bom'] = [{'part': part, 'refs': refs, 'quantity': len(refs)} for part,refs in sorted(bom.items())]
        if isinstance(self.intent['fab_profile'], str):
            self.used.add(self.intent['fab_profile'])
            from .assembly import attach_assembly
            attach_assembly(self.catalog, self.intent)
        else:
            self.refuse('UNKNOWN_INPUT', 'fab_profile', 'Fab profile is unresolved', ('Q9',))

    def inspect(self, value, path):
        if isinstance(value, dict):
            if value.get('status') == 'UNKNOWN':
                self.refuse('UNKNOWN_INPUT', path, value['reason'], value['blocks'])
            if 'source' in value and 'page' in value:
                anchor = {'source':value['source'],'page':value['page']}
                if anchor not in self.intent['evidence']:
                    self.intent['evidence'].append(anchor)
            for key, child in value.items():
                self.inspect(child, path + '.' + key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self.inspect(child, path + '.' + str(index))

    def resolve_dependencies(self):
        # Dependency closure is explicit, including the block and rule authorities.
        try:
            dependencies = dependency_closure(self.catalog, self.used)
            self.intent['dependencies'] = sorted(dependencies)
            self.intent['verification'] = min(
                (self.catalog.get(i)['verification'] for i in dependencies),
                key=LEVELS.index, default='DRAFT'
            )
            for identity in sorted(dependencies):
                record = self.catalog.get(identity)
                self.inspect(record, identity)
                if record['verification'] == 'DRAFT':
                    self.refuse('UNVERIFIED_RECORD', identity, 'Dependency is DRAFT')
            self.inspect(self.graph, 'graph')
            self.inspect(self.brief, 'brief')
            self.inspect(self.intent['manufacturing'], 'manufacturing')
        except (ValueError, KeyError) as error:
            self.refuse('MISSING_RECORD', 'dependencies', error)

    def finalize(self):
        from .intent import electrical_checks
        from .power_sinks import derive_loads
        try:
            derive_loads(self)
        except ValueError as error:
            self.refuse('CHECK_FAILED', 'external_loads', error)
        for check in electrical_checks(self.parts, self.intent['nets'], self.intent.get('external_loads', [])):
            self.intent['checks'].append(check)
            if check['result'] != 'PASS':
                self.refuse('CHECK_FAILED', check['id'], check['reason'])
        self.intent['evidence'].sort(key=lambda a:(a['source'],a['page']))
        self.intent['checks'].sort(key=lambda c:c['id'])
        if not self.intent['refusals']:
            self.intent['status'] = 'EXPANDED'
            try:
                validate_intent(self.catalog, self.intent, bundle_commit=self.bundle_commit)
            except ValueError as error:
                self.intent['status'] = 'REFUSED'
                self.refuse('CHECK_FAILED', 'intent', error)
        self.catalog.structure(self.intent, 'design-intent.schema.json')
        return self.intent

    def run(self):
        try:
            self.validate_graph()
            self.check_power_requirements()
            self.resolve_instances()
            from .parameter_bindings import check_bindings as check_parameters
            check_parameters(self)
            self.unite_nets()
            from .gpio import configure_pins
            configure_pins(self)
            self.assemble_nets()
            from .bringup_contract import project_bringup
            project_bringup(self.graph, self.intent, self.catalog, self.used)
            from .electrical_bindings import check_bindings
            check_bindings(self)
            self.check_source_paths()
            self.apply_layout_rules()
            self.assemble_bom()
        except (ValueError, KeyError, TypeError) as error:
            self.refuse('INVALID_REFERENCE', 'graph', error)
        self.resolve_dependencies()
        return self.finalize()


def expand(catalog, graph, brief, *, bundle_commit):
    """Resolve components, unite port nets and emit typed refusals on unsafe inputs."""
    return _Expansion(catalog, graph, brief, bundle_commit).run()


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
