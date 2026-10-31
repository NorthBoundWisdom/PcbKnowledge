"""Typed brief feasibility screening; eligibility is not graph or A2 acceptance."""
from .catalog import LEVELS, selected_candidate
from .expansion import dependency_closure


def refusal(code, path, reason):
    query = {'UNSATISFIED_SELECTION': 'Q1', 'CHECK_FAILED': 'Q4'}.get(code, 'Q11')
    return {'code': code, 'path': path, 'reason': reason[:256], 'queries': [query]}


def numeric(value):
    return {key: value[key] for key in ('value', 'min', 'typ', 'max', 'unit') if key in value}


def function_parameters(brief, function):
    parameters = dict(function['parameters'])
    for group in ('sources', 'rails'):
        for supply in brief['power'][group]:
            if supply.get('function') != function['id']:
                continue
            for name, field in (('output_voltage', 'voltage'), ('output_current', 'current_budget')):
                value = supply[field]
                if name in parameters and numeric(parameters[name]) != numeric(value):
                    raise ValueError('Function and power binding disagree: ' + name)
                parameters[name] = value
    return parameters


def selected_parts(catalog, block):
    parts = []
    for component in block['components']:
        candidates = catalog._candidates(component['select'])
        if not candidates:
            raise ValueError('No eligible part for component ' + component['ref'])
        parts.append(selected_candidate(candidates))
    return parts


def validate_package_requirement(catalog, function):
    family, role = function.get('package_family'), function.get('package_role')
    if not family and not role:
        return True
    if not family or not role:
        raise ValueError('Package family and package role must be specified together')
    catalog.vocabulary.member('roles', role)
    catalog.vocabulary.member('package-families', family)


def validate_package_requirements(catalog, brief):
    for function in brief['functions']:
        validate_package_requirement(catalog, function)


def package_selection_matches(catalog, function, parts):
    validate_package_requirement(catalog, function)
    family, role = function.get('package_family'), function.get('package_role')
    if not family and not role:
        return True
    return any(role in part['roles'] and catalog.get(part['package'], 'package')['family'] == family
               for part in parts)


def block_eligibility(catalog, block, function, parameters):
    for name, value in parameters.items():
        if name not in block['parameters']:
            return 'CHECK_FAILED', 'Block does not declare requested parameter: ' + name
        declaration = block['parameters'][name]
        catalog.vocabulary.quantity(value, declaration['quantity'])
        if value.get('status') == 'UNKNOWN':
            return 'UNKNOWN_INPUT', 'Requested parameter is unresolved: ' + name
        if 'fixed' in declaration and numeric(value) != numeric(declaration['fixed']):
            return 'CHECK_FAILED', 'Fixed operating parameter differs: ' + name
    parts = selected_parts(catalog, block)
    family = function.get('package_family')
    if not package_selection_matches(catalog, function, parts):
        return 'UNSATISFIED_SELECTION', 'Selected role component does not satisfy package family: ' + str(family)
    identities = {block['id'], *(part['id'] for part in parts)}
    closure = dependency_closure(catalog, identities)
    if any(LEVELS.index(catalog.get(identity)['verification']) < LEVELS.index('AGENT_VERIFIED')
           for identity in closure):
        return 'UNVERIFIED_RECORD', 'Block or selected dependency closure is not independently verified'
    return None


def assess_function(catalog, brief, function):
    path = 'functions.' + function['id']
    category = function.get('category')
    blocks = [record for record in catalog.records.values()
              if record['id'].startswith('block:') and record['category'] == category]
    if not category or not blocks:
        return refusal('UNSATISFIED_SELECTION', path, 'No block provides declared category: ' + str(category))
    try:
        parameters = function_parameters(brief, function)
    except ValueError as error:
        return refusal('CHECK_FAILED', path, str(error))
    from .electrical_bindings import required_ports
    required = required_ports(brief, function['id'])
    reasons = []
    for block in sorted(blocks, key=lambda item: item['id']):
        try:
            reason = block_eligibility(catalog, block, function, parameters)
            if not required <= {port['name'] for port in block['ports']}:
                reason = ('CHECK_FAILED', 'Block lacks an electrically bound function port')
        except (KeyError, ValueError) as error:
            reason = ('UNSATISFIED_SELECTION', str(error))
        if reason is None:
            return None
        reasons.append(reason)
    code, reason = reasons[0]
    return refusal(code, path, 'No eligible block: ' + reason)


def edge_interface_refusals(brief):
    interfaces = [item['id'] for item in brief['interfaces']]
    edges = brief['mechanical']['edge_interfaces']
    results = []
    if len(set(interfaces)) != len(interfaces):
        results.append(refusal('INVALID_REFERENCE', 'interfaces', 'Duplicate interface identities'))
    unknown = sorted(set(edges) - set(interfaces))
    if unknown:
        results.append(refusal('INVALID_REFERENCE', 'mechanical.edge_interfaces',
                               'Edge interface is not declared in brief.interfaces: ' + ', '.join(unknown)))
    if len(set(edges)) != len(edges):
        results.append(refusal('INVALID_REFERENCE', 'mechanical.edge_interfaces',
                               'Duplicate edge interface references'))
    return results


def assess_brief(catalog, brief):
    """Return typed refusals; an empty list means screening passed, not A2 proof."""
    catalog.structure(brief, 'design-brief.schema.json')
    validate_package_requirements(catalog, brief)
    results = edge_interface_refusals(brief)
    from .electrical_bindings import validate_bindings
    try:
        validate_bindings(brief)
    except ValueError as error:
        results.append(refusal('INVALID_REFERENCE', 'electrical_bindings', str(error)))
    function_ids = [function['id'] for function in brief['functions']]
    if len(set(function_ids)) != len(function_ids):
        results.append(refusal('CHECK_FAILED', 'functions', 'Duplicate function identities'))
    for group in ('sources', 'rails'):
        for supply in brief['power'][group]:
            if supply.get('function') not in function_ids:
                results.append(refusal('UNKNOWN_INPUT', 'power.' + group, 'Power requirement lacks function binding'))
    for function in brief['functions']:
        item = assess_function(catalog, brief, function)
        if item:
            results.append(item)
    return results
