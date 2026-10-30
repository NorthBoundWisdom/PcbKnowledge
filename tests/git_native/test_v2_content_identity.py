"""Synthesis content survives rebases, not changed catalog, audit or engine inputs."""
import copy
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pcbknowledge.serialization import canonical_json, read_json
from pcbknowledge.v2.bundle import Bundle, build_bundle, _git
from pcbknowledge.v2.synthesis_identity import input_identity
from pcbknowledge.v2.synthesis_inputs import capture_inputs, resolve_inputs, resolve_replay_inputs
from pcbknowledge.workspace import initialize_workspace

ROOT = Path(__file__).resolve().parents[2]


class ContentIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'original'
        initialize_workspace(self.root, schema_source_root=ROOT, init_git=True)
        _git(self.root, 'config', 'user.name', 'Synthetic')
        _git(self.root, 'config', 'user.email', 'test@example.invalid')
        location = self.root / 'evals/golden-designs'
        location.mkdir(parents=True)
        (location / 'g2.brief.json').write_bytes((ROOT / 'evals/golden-designs/g2.brief.json').read_bytes())
        self.commit('Original synthetic input')
        self.original = build_bundle(self.root)
        self.snapshot = capture_inputs(self.original, 'G2', 'Exact synthetic skill\n')

    def commit(self, message):
        _git(self.root, 'add', '.')
        _git(self.root, 'commit', '-m', message)

    def candidate_document(self, document):
        path = self.root / 'build/candidate.json'
        path.write_bytes(canonical_json(document).encode('utf-8'))
        return path

    def test_new_clone_without_original_commit_resolves_rebased_same_content(self):
        (self.root / 'unrelated.py').write_text('value = 1\n')
        self.commit('Unrelated code outside the engine')
        tree = _git(self.root, 'rev-parse', 'HEAD^{tree}').decode().strip()
        rebased = _git(self.root, 'commit-tree', tree, '-m', 'Published replacement root').decode().strip()
        _git(self.root, 'update-ref', 'refs/heads/published', rebased)
        clone = Path(self.temp.name).resolve() / 'clone'
        global_config = Path(self.temp.name) / 'gitconfig'
        global_config.write_text('[core]\n    autocrlf = true\n', encoding='utf-8')
        environment = {**os.environ, 'GIT_CONFIG_GLOBAL': str(global_config)}
        subprocess.run(['git', 'clone', '-c', 'core.autocrlf=false', '--no-local', '--single-branch',
                        '--branch', 'published', str(self.root), str(clone)],
                       check=True, capture_output=True, env=environment)
        self.assertEqual(_git(clone, 'config', '--local', 'core.autocrlf').strip(), b'false')
        self.assertEqual((clone / 'pcbknowledge.workspace.json').read_bytes(),
                         _git(clone, 'show', 'HEAD:pcbknowledge.workspace.json'))
        absent = subprocess.run(['git', '-C', str(clone), 'cat-file', '-e', self.snapshot['bundle_commit']],
                                capture_output=True)
        self.assertNotEqual(absent.returncode, 0)
        self.assertFalse((clone / '.pcbknowledge/evidence').exists())
        candidate = build_bundle(clone)
        document = resolve_inputs(self.snapshot, candidate)
        self.assertEqual(document['commit'], rebased)
        self.assertNotEqual(document['commit'], self.snapshot['bundle_commit'])
        with Bundle(candidate) as bundle:
            self.assertEqual(input_identity(bundle), self.snapshot['input_identity'])
        self.assertEqual(self.snapshot, capture_inputs(self.original, 'G2', 'Exact synthetic skill\n'))

    def test_registry_catalog_mutation_is_rejected_even_if_still_valid(self):
        path = self.root / 'knowledge/registry/roles.json'
        document = read_json(path.read_bytes())
        document['entries']['synthetic.new-role'] = {'queries': ['Q1']}
        path.write_bytes(canonical_json(document).encode())
        self.commit('Change registry authority')
        candidate = build_bundle(self.root)
        with self.assertRaisesRegex(ValueError, 'catalog or executing engine'):
            resolve_inputs(self.snapshot, candidate)

    def test_audit_input_and_runtime_drift_cannot_use_old_receipt(self):
        path = self.root / 'evals/golden-designs/g2.brief.json'
        document = read_json(path.read_bytes())
        document['title'] += ' revised'
        path.write_bytes(canonical_json(document).encode())
        self.commit('Change brief outside catalog tree')
        candidate = build_bundle(self.root)
        with Bundle(candidate) as bundle:
            self.assertEqual(bundle.catalog_tree, self.snapshot['input_identity']['catalog_tree'])
            self.assertNotEqual(bundle.audit_sha256, self.snapshot['input_identity']['audit_sha256'])
        with self.assertRaises(ValueError):
            resolve_inputs(self.snapshot, candidate)
        with patch('pcbknowledge.v2.synthesis_identity.engine_digest', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'executing engine'):
                resolve_inputs(self.snapshot, self.original)

    def test_missing_authority_changed_blob_and_tree_proofs_are_rejected(self):
        original = read_json(self.original.read_bytes())
        cases = []
        missing = copy.deepcopy(original)
        del missing['files']['schemas/source.schema.json']
        cases.append(missing)
        changed = copy.deepcopy(original)
        changed['files']['schemas/source.schema.json'] += ' '
        cases.append(changed)
        tree = copy.deepcopy(original)
        tree['tree'][0]['oid'] = '0' * 40
        cases.append(tree)
        for document in cases:
            with self.subTest(case=len(document['files'])), self.assertRaises(ValueError):
                resolve_inputs(self.snapshot, self.candidate_document(document))

    def test_snapshot_identity_provenance_skill_and_missing_candidate_fail_closed(self):
        mutations = [('input_identity', {'catalog_tree': 'bad'}), ('bundle_commit', 'bad'),
                     ('bundle_sha256', 'bad'), ('skill_text', 'altered'), ('brief_sha256', '0' * 64)]
        for field, value in mutations:
            with self.subTest(field=field), self.assertRaises(ValueError):
                resolve_inputs({**self.snapshot, field: value}, self.original)
        with self.assertRaisesRegex(ValueError, 'candidate bundle'):
            resolve_inputs(self.snapshot, self.root / 'missing.json')

    def test_explicit_engine_replay_resolution_still_requires_original_content(self):
        original = copy.deepcopy(self.snapshot)
        with patch('pcbknowledge.v2.synthesis_identity.engine_digest', return_value='0' * 64):
            result = resolve_replay_inputs(self.snapshot, self.original)
            self.assertEqual(result['commit'], self.snapshot['bundle_commit'])
            self.assertEqual(self.snapshot, original)
            for key in ('catalog_tree', 'audit_sha256'):
                changed = copy.deepcopy(self.snapshot)
                changed['input_identity'][key] = 'e' * len(changed['input_identity'][key])
                with self.subTest(key=key), self.assertRaises(ValueError):
                    resolve_replay_inputs(changed, self.original)
