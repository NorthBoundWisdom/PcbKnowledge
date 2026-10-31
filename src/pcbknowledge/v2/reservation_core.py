"""Exact derived-copper removal and deterministic finite-domain reservation."""
import hashlib
import json
from pcbknowledge.v2.boardview import children
from pcbknowledge.v2.sexpr import parse, dumps
from pcbknowledge.v2.fanout_emit import append_copper
from pcbknowledge.v2.fanout_solver import segments, _validate


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def node_id(node):
    fields = children(node, 'uuid')
    if len(fields) != 1 or len(fields[0]) != 2:
        raise ValueError('Copper needs one exact UUID')
    return str(fields[0][1])


def copper_index(tree):
    result = {}
    if children(tree, 'group') or children(tree, 'arc'):
        raise ValueError('Grouped or curved copper reservation unsupported')
    for kind in ('segment', 'via'):
        for node in children(tree, kind):
            uid = node_id(node)
            if uid in result:
                raise ValueError('Duplicate copper UUID')
            if 'locked' in [x for x in node if not isinstance(x, list)] or children(node, 'locked'):
                raise ValueError('Locked or explicit-lock copper unsupported')
            result[uid] = node
    return result


def choose(candidates):
    """Pick one exact sampled candidate; never claim domain completeness."""
    if not candidates or len(candidates) > 1024:
        raise ValueError('Reservation needs 1..1024 examined candidates')
    def rank(row):
        _validate(row['candidate'])
        blockers = row['blockers']
        if len({b['uuid'] for b in blockers}) != len(blockers):
            raise ValueError('Duplicate blocker')
        length = sum(((b[0]-a[0])**2 + (b[1]-a[1])**2)**.5 for a, b in segments(row['candidate']))
        return (len(blockers), len({b['net'] for b in blockers}), length,
                json.dumps(row['candidate'], sort_keys=True))
    return min(candidates, key=rank)


def compose(original_text, current_text, proposal):
    if digest(original_text) != proposal['source_sha256'] or digest(current_text) != proposal['current_sha256']:
        raise ValueError('Reservation source changed')
    original, current = parse(original_text), parse(current_text)
    if original[0] != 'kicad_pcb' or current[0] != 'kicad_pcb':
        raise ValueError('Reservation needs native boards')
    index = copper_index(current)
    if children(original, 'net') != children(current, 'net'):
        raise ValueError('Reservation changed complete net authority')
    selected = proposal['selection']
    removed = set()
    for blocker in selected['blockers']:
        uid = blocker['uuid']
        if uid in removed or uid not in index or index[uid] != blocker['node']:
            raise ValueError('Blocker UUID/geometry mismatch or duplicate')
        removed.add(uid)
    request = proposal['request']
    seed_text, seed_receipt = append_copper(original_text, {request['uuid']: selected['candidate']})
    seed_tree = parse(seed_text)
    additions = seed_tree[len(original):]
    if any(node_id(node) in index for node in additions):
        raise ValueError('Seed UUID collides with existing copper')
    kept = [node for node in current if not (isinstance(node, list) and node and
            node[0] in ('segment', 'via') and node_id(node) in removed)]
    output = dumps(kept + additions) + '\n'
    if parse(output) != kept + additions:
        raise ValueError('Reservation serialization changed retained nodes')
    return output, {**seed_receipt, 'source_sha256': proposal['source_sha256'],
                    'current_sha256': proposal['current_sha256'], 'output_sha256': digest(output),
                    'removed': selected['blockers'], 'seed_nodes': additions,
                    'retained_copper_count': len(index)-len(removed),
                    'all_other_nodes_preserved': True, 'native_seed_drc': 'NOT_RUN'}
