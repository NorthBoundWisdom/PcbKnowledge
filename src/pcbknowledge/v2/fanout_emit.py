"""Append original fanout copper without rewriting any authoritative board node."""
import hashlib
import uuid
from pathlib import Path
from .fanout_solver import segments, _validate
from .fanout_native import checked_hash


def append_copper(text, allocation):
    from pcbknowledge.v2.sexpr import Atom, dumps, parse
    from pcbknowledge.v2.boardview import children
    if not isinstance(allocation, dict) or not allocation:
        raise ValueError('Fanout allocation must not be empty')
    tree = parse(text)
    if tree[0] != 'kicad_pcb' or any(children(tree, name) for name in ('segment', 'arc', 'via')):
        raise ValueError('Fanout requires a track-free KiCad source board')
    original = list(tree)
    nets = {row[2]: row[1] for row in children(tree, 'net')}
    source_hash = hashlib.sha256(text.encode()).hexdigest()
    additions = []
    via_ids = []
    for identity, row in sorted(allocation.items()):
        _validate(row)
        if row['net'] not in nets or not row['net']:
            raise ValueError('Fanout references an unknown or empty net')
        for index, (a, b) in enumerate(segments(row)):
            uid = str(uuid.uuid5(uuid.NAMESPACE_URL, source_hash + identity + ':segment:' + str(index)))
            additions.append([Atom('segment'), [Atom('start'), *a], [Atom('end'), *b],
                              [Atom('width'), row['width']], [Atom('layer'), row['layer']],
                              [Atom('net'), Atom(str(nets[row['net']]))], [Atom('uuid'), uid]])
        uid = str(uuid.uuid5(uuid.NAMESPACE_URL, source_hash + identity + ':via'))
        via_ids.append(uid)
        additions.append([Atom('via'), [Atom('at'), *row['end']], [Atom('size'), row['via_diameter']],
                          [Atom('drill'), row['via_drill']], [Atom('layers'), 'F.Cu', 'B.Cu'],
                          [Atom('net'), Atom(str(nets[row['net']]))], [Atom('uuid'), uid]])
    tree.extend(additions)
    result = dumps(tree) + '\n'
    if parse(result)[:len(original)] != original:
        raise ValueError('Fanout serialization changed source board nodes')
    return result, {'added_segments': sum(len(segments(r)) for r in allocation.values()),
                    'added_vias': len(allocation), 'seed_via_uuids': via_ids, 'original_nodes_preserved': True}


def emit(root, source, proposal, output):
    """Write proposal to fresh build output. It is NOT routable until native DRC passes."""
    from pcbknowledge.v2.kicad_bridge import _path
    from pcbknowledge.v2.routing import unchanged_placement, input_fingerprints
    source, output = _path(root, source, exists=True), _path(root, output)
    if source.suffix != '.kicad_pcb' or output.suffix != '.kicad_pcb':
        raise ValueError('Fanout requires KiCad board paths')
    sidecars = [output.with_suffix(suffix) for suffix in ('.kicad_pcb', '.kicad_pro', '.kicad_dru', '.kicad_prl')]
    if any(path.exists() or path.is_symlink() for path in sidecars):
        raise ValueError('Fanout destination and settings must be fresh')
    if proposal['status'] != 'PROPOSAL' or set(proposal['allocation']) != {r['uuid'] for r in proposal['requests']}:
        raise ValueError('Fanout proposal must cover every explicit request exactly')
    checked_hash(source, proposal['source_sha256'])
    if input_fingerprints(source) != proposal['source_files_sha256']:
        raise ValueError('Fanout source settings changed')
    text, receipt = append_copper(source.read_text(), proposal['allocation'])
    output.write_text(text)
    unchanged_placement(source, output)
    checked_hash(source, proposal['source_sha256'])
    if input_fingerprints(source) != proposal['source_files_sha256']:
        raise ValueError('Fanout source settings changed')
    return {**receipt, 'board': str(output), 'source_sha256': proposal['source_sha256'],
            'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'settings_sha256': {output.with_suffix(suffix).name:
                                proposal['source_files_sha256'][str(source.with_suffix(suffix))]
                                for suffix in ('.kicad_pro', '.kicad_dru')},
            'native_seed_drc': 'NOT_RUN', 'routing': 'NOT_RUN'}
