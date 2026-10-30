"""Read-only recovery of exact synthesis inputs from preserved commit metadata and local Git trees."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess

from pcbknowledge.serialization import canonical_json
from .bundle import Bundle, FORMAT, MAX_BUNDLE_BYTES, _git, _oid, _selected, _tree_oid
from .catalog import MAX_RECORD_BYTES


def _hash(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(character in '0123456789abcdef' for character in value))


def _metadata(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get('format') != 'pcbknowledge.synthesis-input.v1':
        raise ValueError('Unsupported synthesis input snapshot')
    commit = snapshot.get('bundle_commit')
    tree = snapshot.get('tree_sha')
    expected = snapshot.get('bundle_sha256')
    raw = snapshot.get('commit_object')
    if not _hash(commit, 40) or not _hash(tree, 40) or not _hash(expected, 64):
        raise ValueError('Invalid preserved synthesis input identities')
    if not isinstance(raw, str) or len(raw.encode('utf-8')) > MAX_RECORD_BYTES:
        raise ValueError('Missing or oversized preserved commit object')
    if _oid('commit', raw.encode('utf-8')) != commit:
        raise ValueError('Preserved commit object identity mismatch')
    if not raw.startswith('tree ' + tree + '\n'):
        raise ValueError('Preserved commit does not name the expected tree')
    return commit, tree, expected, raw


def _tree_document(root, tree):
    entries = []
    files = {}
    listing = _git(root, 'ls-tree', '-rz', '--full-tree', tree)
    if len(listing) > MAX_BUNDLE_BYTES:
        raise ValueError('Oversized synthesis input tree')
    for raw in listing.split(b'\0'):
        if not raw:
            continue
        metadata, name = raw.split(b'\t', 1)
        mode, kind, oid = metadata.decode('ascii').split()
        path = name.decode('utf-8')
        entries.append({'path': path, 'mode': mode, 'oid': oid})
        if not _selected(path):
            continue
        if mode not in ('100644', '100755') or kind != 'blob':
            raise ValueError('Synthesis authority must consist of regular Git blobs')
        size = int(_git(root, 'cat-file', '-s', oid).strip())
        if size > MAX_RECORD_BYTES:
            raise ValueError('Oversized synthesis authority blob')
        payload = _git(root, 'cat-file', 'blob', oid)
        if len(payload) != size or _oid('blob', payload) != oid:
            raise ValueError('Synthesis authority blob identity mismatch')
        files[path] = payload.decode('utf-8')
    if _tree_oid(entries) != tree:
        raise ValueError('Recovered synthesis tree identity mismatch')
    return sorted(entries, key=lambda entry: entry['path']), files


def reconstruct_bundle(root, snapshot):
    """Return the exact validated original document without creating Git objects or files.

    Only the named tree and selected blobs must exist locally (for example via a
    tree-equivalent published commit). The original commit object need not exist
    in Git: its preserved bytes authenticate the original commit identity.
    Current working-tree files and later catalog outcomes are never substituted.
    """
    commit, tree, expected, raw = _metadata(snapshot)
    try:
        entries, files = _tree_document(Path(root), tree)
    except (OSError, UnicodeError, subprocess.SubprocessError) as error:
        raise ValueError('Cannot read preserved synthesis tree/blob objects from local Git') from error
    document = {'format': FORMAT, 'commit': commit, 'commit_object': raw, 'tree': entries, 'files': files}
    payload = canonical_json(document).encode('utf-8')
    if len(payload) > MAX_BUNDLE_BYTES or hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError('Reconstructed synthesis bundle SHA-256 mismatch')
    with Bundle.from_document(document):
        pass
    return document


def capture_inputs(bundle_path, brief_id, skill_text):
    """Record portable content identity; retain the actual author's commit/file provenance."""
    from .synthesis import digest
    from .synthesis_identity import input_identity
    from pcbknowledge.serialization import read_json

    path = Path(bundle_path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BUNDLE_BYTES:
        raise ValueError('Unsafe or oversized input bundle')
    payload = path.read_bytes()
    with Bundle.from_document(read_json(payload)) as bundle:
        if brief_id not in bundle.briefs or not isinstance(skill_text, str) or not skill_text.strip():
            raise ValueError('Snapshot requires an existing brief and exact nonempty skill text')
        return {'format': 'pcbknowledge.synthesis-input.v2', 'input_identity': input_identity(bundle),
                'bundle_commit': bundle.commit, 'bundle_sha256': hashlib.sha256(payload).hexdigest(),
                'brief': brief_id, 'brief_sha256': digest(bundle.briefs[brief_id]),
                'skill_text': skill_text, 'skill_sha256': hashlib.sha256(skill_text.encode('utf-8')).hexdigest()}


def _resolve_inputs(snapshot, candidate_bundle, *, replay):
    """Validate a published content-equivalent bundle without needing the original commit object.

    Returns the candidate's authenticated document, not falsely reconstructed
    original bytes. The snapshot and attempt receipts keep their original hashes.
    """
    from .synthesis import digest
    from .synthesis_identity import match_identity, validate_identity
    from pcbknowledge.serialization import read_json

    fields = {'format', 'input_identity', 'bundle_commit', 'bundle_sha256', 'brief',
              'brief_sha256', 'skill_text', 'skill_sha256'}
    if not isinstance(snapshot, dict) or set(snapshot) != fields:
        raise ValueError('Malformed content-identified synthesis snapshot')
    if snapshot['format'] != 'pcbknowledge.synthesis-input.v2':
        raise ValueError('Unsupported synthesis snapshot format')
    validate_identity(snapshot['input_identity'])
    if not isinstance(snapshot['brief'], str) or not snapshot['brief']:
        raise ValueError('Snapshot requires a brief identity')
    if (not _hash(snapshot['bundle_commit'], 40)
            or any(not _hash(snapshot[key], 64) for key in ('bundle_sha256', 'brief_sha256', 'skill_sha256'))):
        raise ValueError('Invalid snapshot provenance hash')
    skill = snapshot['skill_text']
    if (not isinstance(skill, str) or not skill.strip()
            or hashlib.sha256(skill.encode('utf-8')).hexdigest() != snapshot['skill_sha256']):
        raise ValueError('Snapshot skill identity mismatch')
    path = Path(candidate_bundle)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BUNDLE_BYTES:
        raise ValueError('Unsafe or oversized candidate bundle')
    document = read_json(path.read_bytes())
    with Bundle.from_document(document) as bundle:
        match_identity(bundle, snapshot['input_identity'], replay=replay)
        brief = bundle.briefs.get(snapshot['brief'])
        if brief is None or digest(brief) != snapshot['brief_sha256']:
            raise ValueError('Candidate brief differs from synthesis input')
    return document


def resolve_inputs(snapshot, candidate_bundle):
    """Resolve a published bundle matching the exact original content and engine."""
    return _resolve_inputs(snapshot, candidate_bundle, replay=False)


def resolve_replay_inputs(snapshot, candidate_bundle):
    """Resolve original content for an explicitly labeled replay with the current engine."""
    return _resolve_inputs(snapshot, candidate_bundle, replay=True)
