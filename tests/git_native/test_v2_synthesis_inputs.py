"""Exact historical bundle reconstruction without checking out or rewriting Git objects."""
import copy
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pcbknowledge.serialization import canonical_json, read_json
from pcbknowledge.workspace import initialize_workspace
from pcbknowledge.v2.bundle import _oid, build_bundle
from pcbknowledge.v2.synthesis_inputs import reconstruct_bundle

ROOT = Path(__file__).resolve().parents[2]


class SynthesisInputsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'workspace'
        initialize_workspace(self.root, schema_source_root=ROOT, init_git=True)
        for arguments in (('config', 'user.name', 'Synthetic'), ('config', 'user.email', 'test@example.invalid'),
                          ('add', '.'), ('commit', '-m', 'Original input')):
            subprocess.run(['git', '-C', str(self.root), *arguments], check=True, capture_output=True)
        self.payload = build_bundle(self.root).read_bytes()
        self.document = read_json(self.payload)
        self.snapshot = {'format': 'pcbknowledge.synthesis-input.v1', 'bundle_commit': self.document['commit'],
                         'commit_object': self.document['commit_object'],
                         'tree_sha': self.document['commit_object'].splitlines()[0].split()[1],
                         'bundle_sha256': hashlib.sha256(self.payload).hexdigest()}

    def test_original_bundle_is_byte_identical_despite_dirty_worktree(self):
        (self.root / 'schemas/source.schema.json').write_text('invalid current worktree')
        reconstructed = reconstruct_bundle(self.root, self.snapshot)
        self.assertEqual(canonical_json(reconstructed).encode(), self.payload)
        self.assertEqual((self.root / 'schemas/source.schema.json').read_text(), 'invalid current worktree')

    def test_preserved_commit_need_not_exist_in_local_git(self):
        snapshot = copy.deepcopy(self.snapshot)
        raw = snapshot['commit_object'] + 'Preserved distinct metadata.\n'
        snapshot['commit_object'] = raw
        snapshot['bundle_commit'] = _oid('commit', raw.encode())
        document = {**self.document, 'commit': snapshot['bundle_commit'], 'commit_object': raw}
        payload = canonical_json(document).encode()
        snapshot['bundle_sha256'] = hashlib.sha256(payload).hexdigest()
        check = subprocess.run(['git', '-C', str(self.root), 'cat-file', '-e', snapshot['bundle_commit']],
                               capture_output=True)
        self.assertNotEqual(check.returncode, 0)
        self.assertEqual(canonical_json(reconstruct_bundle(self.root, snapshot)).encode(), payload)
        check = subprocess.run(['git', '-C', str(self.root), 'cat-file', '-e', snapshot['bundle_commit']],
                               capture_output=True)
        self.assertNotEqual(check.returncode, 0)

    def test_wrong_commit_tree_or_bundle_hash_is_refused(self):
        for key, value in (('commit_object', 'bad'), ('tree_sha', '0' * 40),
                           ('bundle_commit', '0' * 40), ('bundle_sha256', '0' * 64)):
            snapshot = {**self.snapshot, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                reconstruct_bundle(self.root, snapshot)

    def test_missing_git_objects_and_corrupt_blob_payload_are_refused(self):
        from pcbknowledge.v2.bundle import _git
        with patch('pcbknowledge.v2.synthesis_inputs._git', side_effect=subprocess.CalledProcessError(128, 'git')):
            with self.assertRaisesRegex(ValueError, 'local Git'):
                reconstruct_bundle(self.root, self.snapshot)
        def corrupted(root, *arguments):
            payload = _git(root, *arguments)
            return payload + b'x' if arguments[:2] == ('cat-file', 'blob') else payload
        with patch('pcbknowledge.v2.synthesis_inputs._git', side_effect=corrupted):
            with self.assertRaisesRegex(ValueError, 'blob identity'):
                reconstruct_bundle(self.root, self.snapshot)
