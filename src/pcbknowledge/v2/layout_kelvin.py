"""Read-only Kelvin branch proof over supported exported copper (D80)."""
from .layout_kelvin_geometry import UnsupportedKelvin, contact, contact_region, end_inside, pad_shape, track_shape

from .layout_kelvin_scope import check_outline, pad_envelope, routing_envelopes, separate_unsupported

MAX_PRIMITIVES = 512
LOAD_TYPES = {'POWER_IN', 'POWER_OUT', 'POWER_SINK', 'GROUND'}


def finding(result, reason):
    return {'kind': 'KELVIN', 'result': result, 'reason': reason}


def primitives(board, nets):
    if board.get('unsupported'):
        raise UnsupportedKelvin('Unprojected board geometry requires a separate proof')
    count = sum(len(board.get(key, [])) for key in ('segments', 'arcs', 'vias', 'zones'))
    count += sum(len(pads) for fp in board['footprints'].values() for pads in fp['pads'].values())
    if count > MAX_PRIMITIVES:
        raise UnsupportedKelvin('Kelvin copper primitive resource bound exceeded')
    shapes, terminals = [], {}
    unsupported = routing_envelopes(board)
    for ref, footprint in board['footprints'].items():
        for number, pads in footprint['pads'].items():
            name = ref + '.pin:' + number
            for pad in pads:
                try:
                    if not number or len(pads) != 1:
                        raise UnsupportedKelvin('Multiple or unnumbered physical pads')
                    shape = pad_shape(pad, name)
                except UnsupportedKelvin:
                    layers = {'*.Cu'} if pad.get('drill') or pad.get('drill_size') else set(pad['layers'])
                    unsupported.append((pad['net'], layers, pad_envelope(pad)))
                    continue
                terminals[name] = len(shapes)
                shapes.append(dict(shape, net=pad['net']))
    shapes.extend(dict(track_shape(track), net=track['net']) for track in board['segments'])
    check_outline(board, shapes, nets)
    separate_unsupported(unsupported, shapes, nets)
    return shapes, terminals


def terminal_types(intent, catalog):
    result = {}
    for component in intent['components']:
        part = catalog.get(component['part'], 'part')
        for pin in part['pins']:
            result[component['ref'] + '.pin:' + pin['number']] = pin['type']
    return result


def branch_graph(shapes, target_index):
    target = shapes[target_index]
    graph = [set() for _ in shapes]
    contacts = set()
    for index, shape in enumerate(shapes):
        if index == target_index:
            continue
        value = contact(shape, target)
        if value == 0:
            raise UnsupportedKelvin('Tangential copper contact requires a separate proof')
        if value > 0:
            if shape['terminal'] is not None:
                raise UnsupportedKelvin('Overlapping terminal and target pads require a separate proof')
            if not end_inside(shape, target):
                raise UnsupportedKelvin('Track crosses or ambiguously touches the target-pad boundary')
            contacts.add(index)
        for other in range(index):
            if other == target_index:
                continue
            value = contact(shape, shapes[other])
            if value == 0:
                raise UnsupportedKelvin('Tangential copper contact requires a separate proof')
            if value > 0 and contact_region(shape, shapes[other], target) == 'OUTSIDE':
                graph[index].add(other)
                graph[other].add(index)
    return graph, contacts


def reachable(graph, start):
    seen, pending = set(), [start]
    while pending:
        index = pending.pop()
        if index not in seen:
            seen.add(index)
            pending.extend(graph[index] - seen)
    return seen


def check_branch(shapes, terminals, branch, types, target_ref, net):
    start, target = terminals[branch['sense']], terminals[branch['target']]
    if shapes[start]['net'] != net or shapes[target]['net'] != net:
        return finding('FAIL', 'Mapped sense and target pad nets differ from the ordered sense net')
    for shape in shapes:
        if contact(shape, shapes[target]) > 0 and shape['net'] != net:
            status = 'FAIL' if shape['net'] else 'NOT_CHECKABLE'
            return finding(status, 'Target-pad copper contact has a different or unassigned net identity')
    graph, contacts = branch_graph(shapes, target)
    reached = reachable(graph, start)
    if any(shapes[index]['net'] != net for index in reached):
        return finding('FAIL', 'Sense branch physically contacts copper assigned to another net')
    other_terminals = {shapes[index]['terminal'] for index in reached
                       if shapes[index]['terminal'] not in (None, branch['sense'])}
    loads = {name for name in other_terminals
             if types.get(name) in LOAD_TYPES or name.split('.pin:')[0] == target_ref}
    if loads:
        names = ', '.join(sorted(loads))
        return finding('FAIL', 'Sense copper reaches a load terminal outside the target pad: ' + names)
    if other_terminals:
        return finding('NOT_CHECKABLE',
                       'Possible input filter or unclassified branch terminal requires a separate proof')
    if not reached & contacts:
        return finding('FAIL', 'No physical routed connection from sense terminal to specified shunt pad')
    return finding('PASS', 'Sense copper reaches its shunt pad without an outside load branch')


def check_kelvin(board, rule, intent, catalog):
    """No mutation; net names never stand in for physical connectivity."""
    try:
        branches = rule.get('branches')
        if not isinstance(branches, list) or len(branches) != 2:
            raise UnsupportedKelvin('Two explicit sense-to-shunt branch mappings are required')
        senses = {branch['sense'] for branch in branches}
        targets = {branch['target'] for branch in branches}
        if len(senses) != 2 or len(targets) != 2 or senses & targets:
            raise UnsupportedKelvin('Distinct sense and shunt terminal mappings required')
        if any(name.split('.pin:')[0] != rule['target'] for name in targets):
            raise UnsupportedKelvin('Mapped target terminals must belong to the declared shunt')
        nets = rule['sense_nets']
        if not isinstance(nets, list) or len(nets) != 2 or len(set(nets)) != 2:
            raise UnsupportedKelvin('Two distinct ordered sense nets are required')
        if any(not isinstance(net, str) or not net for net in nets):
            raise UnsupportedKelvin('Two distinct ordered sense nets are required')
        shapes, terminals = primitives(board, set(nets))
        types = terminal_types(intent, catalog)
        if not senses | targets <= terminals.keys() or not senses | targets <= types.keys():
            raise UnsupportedKelvin('Mapped terminal identity or pin type is missing')
        results = [check_branch(shapes, terminals, branch, types, rule['target'], net)
                   for branch, net in zip(branches, nets)]
        for status in ('FAIL', 'NOT_CHECKABLE'):
            if any(result['result'] == status for result in results):
                return next(result for result in results if result['result'] == status)
        return finding('PASS', 'Both sense branches connect only at their specified shunt pads')
    except (UnsupportedKelvin, KeyError, TypeError, ValueError, IndexError) as error:
        return finding('NOT_CHECKABLE', str(error))
