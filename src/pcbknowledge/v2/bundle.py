"""Deterministic, commit-authenticated catalog snapshots without source originals."""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import subprocess
import tempfile

from pcbknowledge.serialization import canonical_json, read_json
from .catalog import Catalog, DIRECTORIES, MAX_RECORD_BYTES, record_path
from .audit import design_inputs, require_audit
from pcbknowledge.workspace import _load_manifest_bytes, schema_digest
from .schema import ContractSchemas
from .vocabulary import Vocabulary

FORMAT = 'pcbknowledge.bundle.v2'
MAX_BUNDLE_BYTES = 64 * 1024 * 1024


def _git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def _oid(kind, payload):
    return hashlib.sha1(kind.encode() + b' ' + str(len(payload)).encode() + b'\0' + payload).hexdigest()


def _selected(path):
    return (path in ('.gitignore', 'pcbknowledge.workspace.json')
            or path.startswith(('schemas/', 'knowledge/registry/'))
            or any(path.startswith('knowledge/' + directory + '/') for directory in DIRECTORIES.values())
            or (path.startswith('evals/') and path.endswith('.json')))


def _catalog_authority(path):
    return path == 'pcbknowledge.workspace.json' or path.startswith(('knowledge/', 'schemas/'))


def _tree_oid(entries):
    """Reconstruct Git trees, anchoring every selected byte to the claimed commit."""
    tree = {}
    for entry in entries:
        path, mode, oid = entry['path'], entry['mode'], entry['oid']
        parts = PurePosixPath(path).parts
        if (not parts or path != '/'.join(parts) or any(p in ('.', '..', '.git') for p in parts)
                or path.startswith('/') or '\\' in path or '\0' in path):
            raise ValueError('Unsafe bundle tree path')
        if mode not in ('100644', '100755', '120000', '160000') or len(oid) != 40:
            raise ValueError('Invalid Git tree entry')
        try:
            bytes.fromhex(oid)
        except ValueError as error:
            raise ValueError('Invalid Git object identity') from error
        node = tree
        for part in parts[:-1]:
            if part in node and not isinstance(node[part], dict):
                raise ValueError('Conflicting bundle tree paths')
            node = node.setdefault(part, {})
        if parts[-1] in node:
            raise ValueError('Duplicate bundle tree path')
        node[parts[-1]] = (mode, oid)

    def encode(node):
        payload = b''
        for name in sorted(node, key=lambda key: (key + ('/' if isinstance(node[key], dict) else '')).encode()):
            value = node[name]
            mode, oid = ('40000', encode(value)) if isinstance(value, dict) else value
            payload += mode.encode() + b' ' + name.encode() + b'\0' + bytes.fromhex(oid)
        return _oid('tree', payload)
    return encode(tree)


def build_bundle(root, output_dir=None):
    root = Path(root).resolve()
    if _git(root, 'status', '--porcelain', '--untracked-files=all').strip():
        raise ValueError('Bundle requires a clean committed workspace')
    catalog = Catalog(root, root / 'schemas')
    require_audit(catalog)
    commit = _git(root, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    commit_object = _git(root, 'cat-file', 'commit', commit).decode('utf-8')
    entries = []
    files = {}
    for raw in _git(root, 'ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
        if not raw:
            continue
        metadata, name = raw.split(b'\t', 1)
        mode, kind, oid = metadata.decode().split()
        path = name.decode('utf-8')
        entries.append({'path': path, 'mode': mode, 'oid': oid})
        if _selected(path):
            if mode not in ('100644', '100755') or kind != 'blob':
                raise ValueError('Bundle authority must be regular files')
            payload = _git(root, 'cat-file', 'blob', oid)
            if len(payload) > MAX_RECORD_BYTES:
                raise ValueError('Oversized bundle authority')
            files[path] = payload.decode('utf-8')
    document = {'format': FORMAT, 'commit': commit, 'commit_object': commit_object,
                'tree': sorted(entries, key=lambda entry: entry['path']), 'files': files}
    # Re-read from the immutable selected bytes, not the mutable working tree.
    with Bundle.from_document(document) as snapshot:
        if snapshot.catalog.records != catalog.records:
            raise ValueError('Workspace changed during bundle creation')
    if (_git(root, 'rev-parse', 'HEAD').decode().strip() != commit
            or _git(root, 'status', '--porcelain', '--untracked-files=all').strip()):
        raise ValueError('Workspace changed during bundle creation')
    directory = Path(output_dir) if output_dir else root / 'build/bundle'
    for path in (directory, *directory.parents):
        if path.is_symlink():
            raise ValueError('Bundle output path must not contain symlinks')
    output = directory / (commit + '.json')
    if output.is_symlink():
        raise ValueError('Bundle output target must not be a symlink')
    directory.mkdir(parents=True, exist_ok=True)
    payload = canonical_json(document)
    if len(payload.encode('utf-8')) > MAX_BUNDLE_BYTES:
        raise ValueError('Oversized bundle')
    output.write_text(payload, encoding='utf-8', newline='\n')
    return output


class Bundle:
    """Validated read-only projection using the same Catalog semantic validator."""
    def __init__(self, path):
        path = Path(path)
        if path.is_symlink() or path.stat().st_size > MAX_BUNDLE_BYTES:
            raise ValueError('Unsafe or oversized bundle')
        self._load(read_json(path.read_bytes()))

    @classmethod
    def from_document(cls, document):
        result = cls.__new__(cls)
        result._load(document)
        return result

    def _load(self, document):
        self._temporary = None
        try:
            if set(document) != {'format', 'commit', 'commit_object', 'tree', 'files'} or document['format'] != FORMAT:
                raise ValueError('Unsupported bundle format')
            self.commit = document['commit']
            payload = document['commit_object'].encode('utf-8')
            if _oid('commit', payload) != self.commit:
                raise ValueError('Bundle commit identity mismatch')
            first = document['commit_object'].splitlines()[0]
            if first != 'tree ' + _tree_oid(document['tree']):
                raise ValueError('Bundle tree does not belong to commit')
            self.catalog_tree = _tree_oid([entry for entry in document['tree']
                                           if _catalog_authority(entry['path'])])
            entries = {entry['path']: entry for entry in document['tree']}
            expected = {path for path in entries if _selected(path)}
            if set(document['files']) != expected:
                raise ValueError('Bundle is missing or adds authority files')
            self._temporary = tempfile.TemporaryDirectory(prefix='pcbknowledge-bundle-')
            root = Path(self._temporary.name).resolve()
            self._materialize(root, document['files'], entries)
            self.catalog = self._catalog(root, document['files'])
            require_audit(self.catalog)
            graphs, self.briefs = design_inputs(root)
            audit = {'graphs': sorted(graphs, key=canonical_json), 'briefs': self.briefs}
            self.audit_sha256 = hashlib.sha256(canonical_json(audit).encode('utf-8')).hexdigest()
            for brief in self.briefs.values():
                self.catalog.structure(brief, 'design-brief.schema.json')
        except (KeyError, TypeError, AttributeError, IndexError) as error:
            self.close()
            raise ValueError('Malformed bundle structure') from error
        except Exception:
            self.close()
            raise

    @staticmethod
    def _materialize(root, files, entries):
        for path, text in files.items():
            entry = entries[path]
            payload = text.encode('utf-8')
            if entry['mode'] not in ('100644', '100755') or len(payload) > MAX_RECORD_BYTES:
                raise ValueError('Unsafe bundle authority')
            if _oid('blob', payload) != entry['oid']:
                raise ValueError('Bundle file does not match committed blob')
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)

    @staticmethod
    def _catalog(root, files):
        # A snapshot is not a mutable Git workspace. Validate authenticated
        # materialized authority using the same structural/semantic contracts.
        manifest = _load_manifest_bytes((root / 'pcbknowledge.workspace.json').read_bytes(), label='bundle manifest')
        if manifest.schema_digest != schema_digest(root):
            raise ValueError('Bundle workspace schema digest mismatch')
        catalog = Catalog.__new__(Catalog)
        catalog.root = root
        catalog.schemas = ContractSchemas(root / 'schemas')
        catalog.vocabulary = Vocabulary.load(root / 'knowledge/registry', root / 'schemas')
        catalog.records = {}
        for kind, directory in DIRECTORIES.items():
            prefix = 'knowledge/' + directory + '/'
            for path, text in sorted(files.items()):
                if not path.startswith(prefix):
                    continue
                if path.endswith('/.gitkeep') and not text.strip():
                    continue
                if not path.endswith('.json'):
                    raise ValueError('Unexpected bundle authority file')
                record = read_json(text.encode())
                catalog.structure(record, kind.replace('_', '-') + '.schema.json')
                if record_path(root, record['id']) != root / path or canonical_json(record) != text:
                    raise ValueError('Noncanonical bundle record or path')
                if record['id'] in catalog.records:
                    raise ValueError('Duplicate bundle record')
                catalog.records[record['id']] = record
        catalog.validate()
        return catalog

    def close(self):
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
