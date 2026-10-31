"""Authenticate cumulative failed-pad provenance and jointly reallocate from original placement."""
import json
from pathlib import Path
from .fanout_native import checked_hash, propose
from .fanout_solver import allocate


def combine(proposals):
    if not proposals:
        raise ValueError('At least one authenticated failed-board proposal is required')
    first = proposals[0]
    requests, candidates, provenance, physical = {}, {}, {}, {}
    for index, proposal in enumerate(proposals):
        for key in ('rules', 'source_sha256', 'source_files_sha256'):
            if proposal[key] != first[key]:
                raise ValueError('Cumulative repair changed original authority')
        for request in proposal['requests']:
            original_uuid = request['uuid']
            options = proposal['verified_candidates'][original_uuid]
            if not options:
                raise ValueError('Cumulative repair lacks candidates for an explicit request')
            center = options[0].get('pad_center', options[0]['start'])
            identity = (request['reference'], request['pad'], request['net'], tuple(center))
            canonical = physical.setdefault(identity, original_uuid)
            if canonical in requests and requests[canonical] != dict(request, uuid=canonical):
                raise ValueError('Conflicting repeated native UUID across history')
            if canonical in candidates and candidates[canonical] != options:
                raise ValueError('Repeated physical endpoint changed verified geometry')
            requests.setdefault(canonical, dict(request, uuid=canonical))
            candidates.setdefault(canonical, options)
            provenance.setdefault(canonical, []).append({'history_index': index, 'native_uuid': original_uuid})
    result = allocate(candidates, first['rules']['clearance'])
    return {**result, 'status': 'PROPOSAL', 'rules': first['rules'],
            'source_sha256': first['source_sha256'], 'source_files_sha256': first['source_files_sha256'],
            'requests': [requests[k] for k in sorted(requests)], 'endpoint_provenance': provenance,
            'history_statistics': [p.get('candidate_statistics', {}) for p in proposals],
            'verified_candidates': candidates, 'candidate_counts': {k: len(v) for k, v in candidates.items()},
            'native_seed_drc': 'NOT_RUN', 'routing': 'NOT_RUN'}


def propose_history(root, placed, history, intent, catalog, *, placed_sha256):
    from pcbknowledge.v2.kicad_bridge import _path
    if not isinstance(history, list) or not history or len(history) > 8:
        raise ValueError('Fanout history needs 1..8 explicit authenticated attempts')
    proposals, records = [], []
    for entry in history:
        if set(entry) != {'board', 'board_sha256', 'drc', 'drc_sha256', 'requests'}:
            raise ValueError('Malformed failed-board history')
        board = _path(root, entry['board'], exists=True)
        drc_path = _path(root, entry['drc'], exists=True)
        checked_hash(drc_path, entry['drc_sha256'])
        report = json.loads(drc_path.read_text())
        proposals.append(propose(root, placed, board, report, entry['requests'], intent, catalog,
                                 placed_sha256=placed_sha256, prior_sha256=entry['board_sha256']))
        checked_hash(drc_path, entry['drc_sha256'])
        records.append({**entry, 'board': str(board), 'drc': str(drc_path)})
    result = combine(proposals)
    result['history'] = records
    return result
