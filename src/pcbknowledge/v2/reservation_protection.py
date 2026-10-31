"""Exact authenticated seed-only native DSN protection; no native I/O."""
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import re

from .boardview import children, field
from .sexpr import Atom, parse
from .specctra import read_specctra, write_specctra


def _one(node, name):
    rows = children(node, name)
    if len(rows) != 1:
        raise ValueError('Expected exactly one ' + name)
    return rows[0]


def _number(value):
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError('Invalid geometry number') from error
    if not result.is_finite() or abs(result) > 1000000000:
        raise ValueError('Nonfinite/excessive geometry number')
    return result


def _scalar(node, name):
    value = field(node, name)
    if value is None or len(value) != 1:
        raise ValueError('Missing scalar ' + name)
    return value[0]


def _point(values, scale=Decimal(1), invert=False):
    if len(values) != 2:
        raise ValueError('Expected two coordinates')
    x, y = [_number(v) * scale for v in values]
    return (x, -y if invert else y)


def _edge(net, layer, width, a, b):
    if layer not in ('F.Cu', 'B.Cu') or width <= 0 or a == b:
        raise ValueError('Invalid seed edge')
    return net, layer, width, tuple(sorted((a, b)))


def _hash(text, expected):
    actual = hashlib.sha256(text.encode()).hexdigest()
    if actual != expected:
        raise ValueError('Source hash mismatch')
    return actual


def _seed(board, receipt):
    nets = {str(row[1]): str(row[2]) for row in children(board, 'net') if len(row) == 3}
    if len(nets) != len(children(board, 'net')) or len(set(nets.values())) != len(nets):
        raise ValueError('Ambiguous board nets')
    rows = receipt.get('seed_nodes', [])
    if not rows or any(not isinstance(r, list) or r[0] not in ('segment', 'via') for r in rows):
        raise ValueError('Nonempty segment/via seed required')
    edges, vias, uuids = Counter(), Counter(), set()
    for row in rows:
        uuid = _scalar(row, 'uuid')
        matches = [n for n in board[1:] if isinstance(n, list) and field(n, 'uuid') == [uuid]]
        if uuid in uuids or matches != [row]:
            raise ValueError('Seed UUID missing, duplicated, or geometry differs from authenticated board')
        uuids.add(uuid)
        net = nets.get(str(_scalar(row, 'net')))
        if not net:
            raise ValueError('Unknown or empty seed net')
        if row[0] == 'segment':
            edges[_edge(net, _scalar(row, 'layer'), _number(_scalar(row, 'width')),
                        _point(field(row, 'start', [])), _point(field(row, 'end', [])))] += 1
        else:
            if field(row, 'layers') != ['F.Cu', 'B.Cu']:
                raise ValueError('Seed via must span both layers')
            diameter, drill = [_number(_scalar(row, k)) for k in ('size', 'drill')]
            if not 0 < drill < diameter:
                raise ValueError('Invalid seed via dimensions')
            vias[(net, _point(field(row, 'at', [])), diameter, drill)] += 1
    if any(v != 1 for v in (*edges.values(), *vias.values())):
        raise ValueError('Duplicate seed geometry')
    if sum(edges.values()) != receipt.get('added_segments') or sum(vias.values()) != receipt.get('added_vias'):
        raise ValueError('Receipt seed counts disagree')
    return edges, vias, set(nets.values()) - {''}


def _via_key(row, library, scale, net):
    if len(row) < 6:
        raise ValueError('Malformed DSN via')
    match = re.fullmatch(r'Via\[0-1\]_(\d+):(\d+)_um', str(row[1]))
    stacks = [p for p in children(library, 'padstack') if p[1] == row[1]]
    if not match or len(stacks) != 1:
        raise ValueError('Unknown/ambiguous native via padstack')
    diameter, drill = [Decimal(v) / 1000 for v in match.groups()]
    expected = {('F.Cu', diameter), ('B.Cu', diameter)}
    shapes = []
    for shape in children(stacks[0], 'shape'):
        circle = shape[1] if len(shape) == 2 else []
        if len(circle) != 3 or circle[0] != 'circle':
            raise ValueError('Unsupported via shape')
        shapes.append((str(circle[1]), _number(circle[2]) * scale))
    if len(shapes) != 2 or set(shapes) != expected or not 0 < drill < diameter:
        raise ValueError('Via shape/identifier dimensions disagree')
    return net, _point(row[2:4], scale, True), diameter, drill


def _matches(tree, edges, vias, nets):
    unit = _scalar(tree, 'unit')
    if unit not in ('um', 'mm'):
        raise ValueError('Unsupported native DSN unit')
    scale = Decimal('.001') if unit == 'um' else Decimal(1)
    library, wiring = _one(tree, 'library'), _one(tree, 'wiring')
    selected, seen_edges, seen_vias = [], Counter(), Counter()
    network_nets = [str(n[1]) for n in children(_one(tree, 'network'), 'net')]
    if len(network_nets) != len(set(network_nets)) or set(network_nets) != nets:
        raise ValueError('DSN network does not match authenticated board nets')
    for row in wiring[1:]:
        if not isinstance(row, list) or row[0] not in ('wire', 'via'):
            raise ValueError('Unsupported wiring item')
        expected = {'path', 'net', 'type'} if row[0] == 'wire' else {'net', 'type'}
        nested = [part[0] for part in row[1:] if isinstance(part, list) and part]
        if set(nested) != expected or len(nested) != len(expected):
            raise ValueError('Unsupported or duplicate wiring fields')
        if (row[0] == 'wire' and len(row) != 4) or (row[0] == 'via' and len(row) != 6):
            raise ValueError('Malformed wiring item fields')
        net = str(_scalar(row, 'net'))
        if net not in nets or _scalar(row, 'type') != 'normal':
            raise ValueError('Unknown net or non-normal source routing state')
        if row[0] == 'via':
            key = _via_key(row, library, scale, net)
            if key in vias:
                seen_vias[key] += 1
                selected.append(row)
            continue
        path = _one(row, 'path')
        if len(path) < 7 or len(path) % 2 != 1:
            raise ValueError('Malformed DSN wire path')
        points = [_point(path[i:i + 2], scale, True) for i in range(3, len(path), 2)]
        keys = [_edge(net, path[1], _number(path[2]) * scale, a, b) for a, b in zip(points, points[1:])]
        overlaps = [k in edges for k in keys]
        if any(overlaps):
            if not all(overlaps):
                raise ValueError('Seed wire mixed with nonseed bulk geometry')
            seen_edges.update(keys)
            selected.append(row)
    if seen_edges != edges or seen_vias != vias:
        raise ValueError('Missing, duplicate, or partial exact seed coverage')
    return selected


def protect_seed(dsn_text, seed_board_text, receipt, *, expected_board_sha256, expected_dsn_sha256):
    """Return (DSN text, proof); only exact complete seed wire/via type fields change.

    Caller must authenticate receipt and hashes via the reservation transaction;
    a matching hash proves byte identity, not that an arbitrary receipt is trusted.
    Collinear export simplification is deliberately unsupported: fail closed.
    """
    board_hash = _hash(seed_board_text, expected_board_sha256)
    dsn_hash = _hash(dsn_text, expected_dsn_sha256)
    if board_hash != receipt.get('output_sha256'):
        raise ValueError('Receipt output hash mismatch')
    board, tree = parse(seed_board_text), read_specctra(dsn_text)
    if board[0] != 'kicad_pcb' or tree[0] != 'pcb':
        raise ValueError('Wrong source document root')
    edges, vias, nets = _seed(board, receipt)
    selected = _matches(tree, edges, vias, nets)
    for row in selected:
        _one(row, 'type')[1] = Atom('protect')
    output = write_specctra(tree)
    return output, {'status': 'PASS', 'source_board_sha256': board_hash, 'source_dsn_sha256': dsn_hash,
                    'output_dsn_sha256': hashlib.sha256(output.encode()).hexdigest(),
                    'protected_wires': sum(r[0] == 'wire' for r in selected),
                    'protected_vias': sum(r[0] == 'via' for r in selected),
                    'seed_segments': sum(edges.values()), 'only_type_fields_changed': True}


def verify_seed_retention(seed_board_text, final_board_text, receipt):
    """Native import regenerates UUIDs; compare exact net/geometry, reject duplicates."""
    _hash(seed_board_text, receipt['output_sha256'])
    expected_edges, expected_vias, nets = _seed(parse(seed_board_text), receipt)
    final = parse(final_board_text)
    rows = children(final, 'segment') + children(final, 'via')
    if children(final, 'arc'):
        raise ValueError('Unsupported final copper arcs')
    actual_receipt = dict(seed_nodes=rows, added_segments=len(children(final, 'segment')),
                          added_vias=len(children(final, 'via')))
    edges, vias, final_nets = _seed(final, actual_receipt)
    if nets != final_nets:
        raise ValueError('Final net authority changed')
    if any(edges[key] != count for key, count in expected_edges.items()) or any(
            vias[key] != count for key, count in expected_vias.items()):
        raise ValueError('Final copper lost or changed protected seed geometry')
    return dict(status='PASS', seed_segments=sum(expected_edges.values()),
                seed_vias=sum(expected_vias.values()), duplicate_copper=0)
