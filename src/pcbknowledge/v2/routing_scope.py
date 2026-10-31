"""Preserve connected unrelated copper while routing only authenticated displaced nets."""
import hashlib
import json
from pcbknowledge.v2.sexpr import Atom, parse
from pcbknowledge.v2.boardview import children, field
from pcbknowledge.v2.specctra import read_specctra, write_specctra
from .reservation_core import copper_index, node_id
from .reservation_protection import _seed


def _hash(text, expected):
    if hashlib.sha256(text.encode()).hexdigest() != expected:
        raise ValueError('Routing-scope source fingerprint mismatch')


def _net(node, nets):
    values = field(node, 'net', [])
    if not values or str(values[0]) not in nets or not nets[str(values[0])]:
        raise ValueError('Scoped copper references an unknown or empty net')
    return nets[str(values[0])]


def _authority(seed_text, current_text, baseline_text, receipt):
    _hash(seed_text, receipt['output_sha256'])
    _hash(current_text, receipt['current_sha256'])
    _hash(baseline_text, receipt['baseline_drc_sha256'])
    source, seed = parse(current_text), parse(seed_text)
    if not source or not seed or source[0]!='kicad_pcb' or seed[0]!='kicad_pcb':
        raise ValueError('Scoped projection requires native board roots')
    index = copper_index(source)
    _seed(seed, receipt)
    nets = {str(row[1]): str(row[2]) for row in children(source, 'net') if len(row) == 3}
    if len(nets) != len(children(source, 'net')) or len(set(nets.values())) != len(nets):
        raise ValueError('Malformed or ambiguous source net authority')
    if children(source, 'net') != children(seed, 'net'):
        raise ValueError('Seed changed source nets')
    removed = set()
    affected = set()
    for row in receipt['removed']:
        key = row['uuid']
        if key in removed or key not in index or index[key] != row['node']:
            raise ValueError('Removed copper UUID/geometry provenance mismatch')
        net = _net(row['node'], nets)
        if row['net'] != net:
            raise ValueError('Removed copper net provenance mismatch')
        affected.add(net)
        removed.add(key)
    affected.update(_net(node, nets) for node in receipt['seed_nodes'])
    retained = [node for node in source if not (isinstance(node, list) and node and
                node[0] in ('segment', 'via') and node_id(node) in removed)]
    if retained + receipt['seed_nodes'] != seed:
        raise ValueError('Seed differs from exact removal/addition source projection')
    _baseline(json.loads(baseline_text), source, nets, affected)
    return affected, set(nets.values()) - {''}


def _baseline(report, source, nets, affected):
    native = report.get('report', {})
    count = sum(len(native.get(k, [])) for k in ('violations', 'unconnected_items', 'schematic_parity'))
    if (report.get('drc_status') != 'FAIL' or report.get('exit_code') != 5
            or report.get('finding_count') != count or not native.get('unconnected_items')
            or native.get('violations') or native.get('schematic_parity')):
        raise ValueError('Scoped source needs a connectivity-only native failed baseline')
    items = children(source, 'segment') + children(source, 'via')
    items += [pad for footprint in children(source, 'footprint') for pad in children(footprint, 'pad')]
    by_uuid = {}
    for item in items:
        key = node_id(item)
        if key in by_uuid:
            raise ValueError('Duplicate source item UUID')
        by_uuid[key] = item
    for finding in native['unconnected_items']:
        items = finding.get('items', [])
        if len(items) != 2 or len({item.get('uuid') for item in items}) != 2:
            raise ValueError('Malformed native unconnected pair')
        for item in items:
            key = item.get('uuid')
            if key not in by_uuid or _net(by_uuid[key], nets) not in affected:
                raise ValueError('Unconnected baseline net lies outside movable affected scope')


def freeze_unaffected(dsn_text, seed_text, current_text, baseline_text, receipt, seed_protection, *,
                      expected_dsn_sha256):
    """Change only normal→protect outside seed/displaced nets; never unlock copper."""
    _hash(dsn_text, expected_dsn_sha256)
    if (seed_protection.get('output_dsn_sha256') != expected_dsn_sha256
            or seed_protection.get('source_board_sha256') != receipt['output_sha256']
            or seed_protection.get('only_type_fields_changed') is not True
            or seed_protection.get('protected_vias') != receipt['added_vias']):
        raise ValueError('Exact seed-protection proof does not bind this DSN')
    affected, nets = _authority(seed_text, current_text, baseline_text, receipt)
    tree = read_specctra(dsn_text)
    network, wiring = children(tree, 'network'), children(tree, 'wiring')
    if not tree or tree[0] != 'pcb' or len(network) != 1 or len(wiring) != 1:
        raise ValueError('Expected one DSN network and wiring scope')
    names = [row[1] for row in children(network[0], 'net') if len(row) >= 2]
    if len(names) != len(children(network[0], 'net')) or len(names) != len(set(names)) or set(names) != nets:
        raise ValueError('DSN net authority changed')
    counts = {}
    for node in children(wiring[0], 'wire') + children(wiring[0], 'via'):
        net_fields, types = children(node, 'net'), children(node, 'type')
        if len(net_fields) != 1 or len(net_fields[0]) != 2 or net_fields[0][1] not in nets:
            raise ValueError('Unknown or malformed DSN copper net')
        if len(types) != 1 or len(types[0]) != 2 or not isinstance(types[0][1], Atom):
            raise ValueError('Missing/duplicate/malformed DSN copper fixed state')
        state, net = types[0][1], str(net_fields[0][1])
        if state not in ('normal', 'protect', 'fix', 'shoveFixed', 'shove_fixed'):
            raise ValueError('Unsupported DSN copper fixed state')
        changed = net not in affected and state == 'normal'
        if changed:
            types[0][1] = Atom('protect')
        row = counts.setdefault(net, {'frozen': 0, 'movable': 0, 'preserved_fixed': 0})
        row['frozen' if changed else 'movable' if state == 'normal' else 'preserved_fixed'] += 1
    output = write_specctra(tree)
    return output, dict(status='PASS', affected_nets=sorted(affected), per_net=counts,
                        dsn_input_sha256=expected_dsn_sha256,
                        dsn_output_sha256=hashlib.sha256(output.encode()).hexdigest(),
                        source_sha256=receipt['current_sha256'], seed_sha256=receipt['output_sha256'])


def verify_scope_retention(seed_text, final_text, receipt, scope_proof):
    """Unrelated existing copper stays exact, not merely same-net connected."""
    _hash(seed_text, receipt['output_sha256'])
    seed, final = parse(seed_text), parse(final_text)
    nets = {str(n[1]): str(n[2]) for n in children(seed, 'net')}
    affected = {_net(row, nets) for row in receipt['seed_nodes']}
    affected.update(_net(row['node'], nets) for row in receipt['removed'])
    if (scope_proof['status'] != 'PASS' or set(scope_proof['affected_nets']) != affected
            or scope_proof['seed_sha256'] != receipt['output_sha256']):
        raise ValueError('Routing scope receipt changed')
    snapshots = []
    for board in (seed, final):
        if children(board, 'arc'):
            raise ValueError('Unsupported scoped copper arcs')
        rows = children(board, 'segment') + children(board, 'via')
        whole = dict(seed_nodes=rows, added_segments=len(children(board, 'segment')),
                     added_vias=len(children(board, 'via')))
        edges, vias, names = _seed(board, whole)
        snapshots.append(({key: value for key, value in edges.items() if key[0] not in affected},
                          {key: value for key, value in vias.items() if key[0] not in affected}, names))
    if snapshots[0] != snapshots[1]:
        raise ValueError('Router changed frozen unrelated copper geometry or net authority')
    return dict(status='PASS', unaffected_segments=sum(snapshots[0][0].values()),
                unaffected_vias=sum(snapshots[0][1].values()), exact_geometry=True)
