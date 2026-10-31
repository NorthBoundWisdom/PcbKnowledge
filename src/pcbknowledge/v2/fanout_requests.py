"""Tool-free failed-pad selection from an authenticated native board/DRC pair."""
from pcbknowledge.v2.boardview import children, field, point, number, transform
from pcbknowledge.v2.sexpr import parse


def extract_requests(board_text, drc):
    tree = parse(board_text)
    if tree[0] != 'kicad_pcb':
        raise ValueError('Expected native KiCad board')
    nets = {row[1]: row[2] for row in children(tree, 'net')}
    pads, all_uuids, physical = {}, set(), {}

    def visit(node):
        for item in node[1:]:
            if not isinstance(item, list) or not item:
                continue
            if item[0] == 'uuid':
                if len(item) != 2 or item[1] in all_uuids:
                    raise ValueError('Malformed or duplicate native UUID')
                all_uuids.add(item[1])
            else:
                visit(item)
    visit(tree)
    for footprint in children(tree, 'footprint'):
        refs = [p[2] for p in children(footprint, 'property') if len(p) >= 3 and p[1] == 'Reference']
        if len(refs) != 1:
            raise ValueError('Native footprint needs exactly one reference')
        origin = field(footprint, 'at', ['0', '0'])
        angle = number(origin[2]) if len(origin) > 2 else 0
        for pad in children(footprint, 'pad'):
            uuid = field(pad, 'uuid')
            net = field(pad, 'net', ['0'])
            if len(pad) < 4 or not uuid or len(uuid) != 1 or net[0] not in nets:
                raise ValueError('Malformed native pad identity')
            pads[uuid[0]] = {'uuid': uuid[0], 'reference': refs[0], 'pad': pad[1],
                             'net': nets[net[0]], 'kind': pad[2]}
            position = transform(point(field(pad, 'at', ['0', '0'])), point(origin), angle)
            physical[uuid[0]] = [refs[0], pad[1], nets[net[0]], *[round(v, 6) for v in position]]
    selected, excluded, other = {}, {}, set()
    for finding in drc['report']['unconnected_items']:
        if finding.get('type') != 'unconnected_items':
            raise ValueError('Unsupported native connectivity finding')
        for item in finding['items']:
            uuid = item.get('uuid')
            if uuid not in all_uuids:
                raise ValueError('DRC item UUID absent from authenticated native board')
            if uuid not in pads:
                other.add(uuid)
                continue
            record = dict(pads[uuid])
            kind = record.pop('kind')
            if kind == 'smd' and record['net']:
                selected[uuid] = record
            else:
                excluded[uuid] = dict(record, reason='Not a netted single-side SMT candidate', pad_kind=kind)
    return {'requests': [selected[k] for k in sorted(selected)],
            'physical_ids': {k: physical[k] for k in sorted(selected)},
            'excluded_pads': [excluded[k] for k in sorted(excluded)], 'nonpad_items': sorted(other)}
