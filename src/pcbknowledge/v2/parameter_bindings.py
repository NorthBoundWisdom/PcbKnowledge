"""One brief-owned operating quantity shared by exact function inputs."""
from .calculators import bounds


def validate_bindings(brief, catalog=None):
    bindings = brief.get('parameter_bindings', [])
    functions = {item['id']: item for item in brief['functions']}
    if len(functions) != len(brief['functions']):
        raise ValueError('Parameter bindings require unique function identities')
    identities, endpoints = set(), set()
    for binding in bindings:
        if binding['id'] in identities:
            raise ValueError('Duplicate parameter binding identity')
        identities.add(binding['id'])
        quantity = binding['value']
        bounds(quantity, quantity.get('unit'), binding['id'])
        if len(binding['endpoints']) < 2:
            raise ValueError('A shared parameter requires at least two endpoints')
        for endpoint in binding['endpoints']:
            function = functions.get(endpoint['function'])
            if function is None or function['count'] != 1:
                raise ValueError('Parameter binding function is absent or not unique')
            key = endpoint['function'], endpoint['parameter']
            if key in endpoints:
                raise ValueError('Parameter binding endpoint appears more than once')
            endpoints.add(key)
            if endpoint['parameter'] in function['parameters']:
                raise ValueError('Shared quantity must not be duplicated in function parameters')
            if catalog is not None:
                catalog.vocabulary.parameters({endpoint['parameter']: quantity})
    return bindings


def parameters_for(brief, function):
    """Project shared inputs without changing either authority object."""
    result = dict(function['parameters'])
    for binding in validate_bindings(brief):
        for endpoint in binding['endpoints']:
            if endpoint['function'] == function['id']:
                result[endpoint['parameter']] = binding['value']
    return result


def _sources(value, catalog, used):
    if isinstance(value, dict):
        if 'source' in value and 'page' in value:
            catalog.evidence(value)
            used.add(value['source'])
        for child in value.values():
            _sources(child, catalog, used)
    elif isinstance(value, list):
        for child in value:
            _sources(child, catalog, used)


def check_bindings(state):
    """Graph copies must preserve the full quantity, conditions and provenance."""
    for binding in validate_bindings(state.brief, state.catalog):
        _sources(binding['value'], state.catalog, state.used)
        passed = True
        for endpoint in binding['endpoints']:
            instances = [item for item in state.instances.values()
                         if endpoint['function'] in item['requirements']]
            if len(instances) != 1:
                raise ValueError('Parameter binding requires one actual function instance')
            supplied = instances[0]['parameters'].get(endpoint['parameter'])
            passed = passed and supplied == binding['value']
        identity = 'parameter-binding:' + binding['id']
        reason = ('Shared function inputs preserve the brief quantity' if passed else
                  'Shared function input differs from the brief quantity')
        state.intent['checks'].append({'id': identity, 'result': 'PASS' if passed else 'FAIL', 'reason': reason})
        if not passed:
            state.refuse('CHECK_FAILED', 'parameter_bindings.' + binding['id'], reason)
