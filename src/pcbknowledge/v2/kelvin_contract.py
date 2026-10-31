"""Explicit source-backed Kelvin endpoints; absent legacy mapping is not physical proof."""


def validate_kelvin(rule, components, connections=None):
    if rule.get('kind') != 'KELVIN' or 'branches' not in rule:
        return
    branches = rule['branches']
    nets = rule.get('sense_nets')
    if not isinstance(branches, list) or len(branches) != 2 or not isinstance(nets, list) or len(nets) != 2:
        raise ValueError('Kelvin requires exactly two ordered branches and sense nets')
    if len(set(nets)) != 2:
        raise ValueError('Kelvin branch nets must remain distinct')
    senses, targets = [], []
    for index, branch in enumerate(branches):
        if not isinstance(branch, dict) or set(branch) != {'sense', 'target', 'evidence'}:
            raise ValueError('Kelvin branch requires exact endpoints and source evidence')
        evidence = branch['evidence']
        if (not isinstance(evidence, dict) or set(evidence) != {'source', 'page'}
                or not isinstance(evidence['source'], str) or not evidence['source'].startswith('source:')
                or type(evidence['page']) is not int or evidence['page'] < 1):
            raise ValueError('Kelvin branch requires a source/page anchor')
        for field, collection in (('sense', senses), ('target', targets)):
            endpoint = branch[field]
            if not isinstance(endpoint, str):
                raise ValueError('Kelvin endpoint must be a numbered physical pin')
            ref, marker, number = endpoint.partition('.pin:')
            if not marker or ref not in components or not number:
                raise ValueError('Kelvin endpoint must be a numbered physical pin')
            if any(number not in {pin['number'] for pin in part['pins']} for part in components[ref]):
                raise ValueError('Kelvin endpoint must use an exact pin number')
            if field == 'sense' and any(
                    next(pin for pin in part['pins'] if pin['number'] == number)['type'] != 'ANALOG'
                    for part in components[ref]):
                raise ValueError('Kelvin sense endpoint must be a typed analog input')
            if connections is not None and connections.get((ref, number)) != nets[index]:
                raise ValueError('Kelvin ordered branch does not match its declared sense net')
            collection.append((ref, number))
    if (len(set(senses)) != 2 or len(set(targets)) != 2 or set(senses) & set(targets)
            or len({ref for ref, _ in senses}) != 1
            or any(ref != rule['target'] for ref, _ in targets)):
        raise ValueError('Kelvin requires distinct sense pins and opposite terminals of the target')


def block_connections(block, components):
    result = {}
    for net in block['nets']:
        for endpoint in net['connect']:
            ref, marker, name = endpoint.partition('.pin:')
            if not marker:
                continue
            numbers = {pin['number'] for part in components[ref] for pin in part['pins']
                       if name in (pin['name'], pin['number'])}
            if len(numbers) != 1:
                raise ValueError('Ambiguous numbered block endpoint')
            key = (ref, numbers.pop())
            if key in result and result[key] != net['name']:
                raise ValueError('Physical block pin appears on multiple nets')
            result[key] = net['name']
    return result


def prefix_branches(rule, instance):
    for branch in rule.get('branches', []):
        for key in ('sense', 'target'):
            branch[key] = instance + '_' + branch[key]
