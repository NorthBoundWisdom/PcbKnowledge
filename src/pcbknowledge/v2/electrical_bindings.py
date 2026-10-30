"""Brief-owned functional net relations, independent of graph labels and instance names."""


def validate_bindings(brief):
    bindings = brief.get('electrical_bindings', [])
    functions = {item['id']: item for item in brief['functions']}
    if len(functions) != len(brief['functions']):
        raise ValueError('Electrical bindings require unique brief function identities')
    identities, endpoints = set(), set()
    for binding in bindings:
        if binding['id'] in identities:
            raise ValueError('Duplicate electrical binding identity: ' + binding['id'])
        identities.add(binding['id'])
        for endpoint in binding['endpoints']:
            function = functions.get(endpoint['function'])
            if function is None:
                raise ValueError('Electrical binding names an unknown function: ' + endpoint['function'])
            if function['count'] != 1:
                raise ValueError('Electrical binding requires a unique function occurrence: ' + function['id'])
            key = endpoint['function'], endpoint['port']
            if key in endpoints:
                raise ValueError('Electrical binding endpoint appears more than once: ' + '.'.join(key))
            endpoints.add(key)
    return bindings


def required_ports(brief, function_id):
    return {endpoint['port'] for binding in brief.get('electrical_bindings', [])
            for endpoint in binding['endpoints'] if endpoint['function'] == function_id}


def check_bindings(state):
    """Use union-find roots and physical pin membership, not requested net labels."""
    bindings = validate_bindings(state.brief)
    used_roots = {}
    physical_roots = {state.find(node) for node in state.pin_nodes.values()}
    for binding in bindings:
        path = 'electrical_bindings.' + binding['id']
        roots = set()
        for endpoint in binding['endpoints']:
            instances = [identity for identity, instance in state.instances.items()
                         if endpoint['function'] in instance['requirements']]
            if len(instances) != 1:
                raise ValueError('Electrical binding function instance is absent or ambiguous: ' + endpoint['function'])
            key = instances[0], endpoint['port']
            if key not in state.port_nodes:
                raise ValueError('Electrical binding selected block lacks port: ' + '.'.join(key))
            root = state.find(state.port_nodes[key])
            if root not in physical_roots:
                raise ValueError('Electrical binding port has no physical net: ' + '.'.join(key))
            roots.add(root)
        passed = len(roots) == 1
        reason = 'Required function ports share one physical net'
        if not passed:
            reason = 'Required function ports are on different physical nets'
        elif next(iter(roots)) in used_roots:
            passed = False
            reason = 'Distinct functional electrical bindings are shorted: ' + used_roots[next(iter(roots))]
        if len(roots) == 1:
            used_roots[next(iter(roots))] = binding['id']
        state.intent['checks'].append({'id': 'electrical-binding:' + binding['id'],
                                       'result': 'PASS' if passed else 'FAIL', 'reason': reason})
        if not passed:
            state.refuse('CHECK_FAILED', path, reason)
