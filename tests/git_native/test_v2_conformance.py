"""Portable original vectors preserve negative expectations and real bundle replay."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from configs.pcbknowledge_conformance import load_manifest, run, run_measurements, validate_context
from pcbknowledge.v2.bundle import build_bundle
from pcbknowledge.workspace import initialize_workspace

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'configs/pcbknowledge_conformance.py'
MANIFEST = 'evals/conformance/manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name).resolve()
        cls.root = cls.directory / 'workspace'
        initialize_workspace(cls.root, schema_source_root=ROOT, init_git=True)
        for folder in ('knowledge', 'evals'):
            shutil.copytree(ROOT / folder, cls.root / folder, dirs_exist_ok=True)
        target = cls.root / 'tests/fixtures/layout/native'
        shutil.copytree(ROOT / 'tests/fixtures/layout/native', target)
        for arguments in [('config', 'user.name', 'Conformance test'),
                          ('config', 'user.email', 'conformance@example.invalid'),
                          ('add', '.'), ('commit', '-m', 'Original catalog replay fixture')]:
            subprocess.run(['git', '-C', str(cls.root), *arguments], check=True, capture_output=True)
        cls.bundle = build_bundle(cls.root, cls.directory / 'bundle')
        cls.original = (cls.root / MANIFEST).read_bytes()

    def setUp(self):
        self.path = self.root / MANIFEST
        self.path.write_bytes(self.original)
        self.addCleanup(self.path.write_bytes, self.original)
        self.manifest = json.loads(self.original)

    def reject(self, manifest):
        self.path.write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaises((ValueError, TypeError)):
            load_manifest(self.root, MANIFEST)

    def test_all_sixteen_kinds_preserve_positive_negative_and_unknown_results(self):
        manifest, tracked = load_manifest(self.root, MANIFEST)
        before = {path: sha(path) for path in tracked}
        result = run_measurements(self.root, manifest)
        self.assertEqual((result['total'], result['matched']), (20, 20))
        self.assertEqual(result['status_counts'], {'PASS': 13, 'FAIL': 2, 'NOT_CHECKABLE': 5})
        self.assertEqual(len(result['per_kind']), 16)
        for kind in ('CLEARANCE_MIN', 'DIFFERENTIAL_PAIR', 'ORIENTATION', 'TEST_POINT'):
            self.assertEqual(result['per_kind'][kind]['status_counts'], {'PASS': 0, 'FAIL': 0, 'NOT_CHECKABLE': 1})
        self.assertEqual(result['per_kind']['RETURN_PATH']['check_count'], 3)
        self.assertEqual(result['per_kind']['RETURN_PATH']['not_checkable_fraction'], 1 / 3)
        self.assertEqual(before, {path: sha(path) for path in tracked})

    def test_unknown_version_and_extra_owned_fields(self):
        for key, value in [('schema', 'future'), ('extra', True)]:
            value_manifest = deepcopy(self.manifest)
            value_manifest[key] = value
            self.reject(value_manifest)

    def test_missing_registry_kind_refuses_even_when_totals_rebalanced(self):
        self.manifest['measurement_cases'].pop()
        self.manifest['expected_status_counts']['NOT_CHECKABLE'] -= 1
        self.reject(self.manifest)

    def test_tampered_board_or_context_hash(self):
        for key in ('board', 'context'):
            value = deepcopy(self.manifest)
            value['measurement_cases'][0][key]['sha256'] = '0' * 64
            self.reject(value)

    def test_paths_refuse_escape_absolute_and_noncanonical_alias(self):
        for path in ('../outside.kicad_pcb', '/tmp/board.kicad_pcb',
                     'tests/../tests/fixtures/layout/native/simple-routed.kicad_pcb',
                     'tests//fixtures/layout/native/simple-routed.kicad_pcb'):
            value = deepcopy(self.manifest)
            value['measurement_cases'][0]['board']['path'] = path
            self.reject(value)

    def test_symlink_board_refused_even_with_matching_hash(self):
        link = self.root / 'tests/fixtures/layout/native/alias.kicad_pcb'
        link.symlink_to('simple-routed.kicad_pcb')
        self.addCleanup(link.unlink)
        self.manifest['measurement_cases'][0]['board']['path'] = link.relative_to(self.root).as_posix()
        self.reject(self.manifest)

    def test_duplicate_case_and_rule_ids_refused(self):
        value = deepcopy(self.manifest)
        value['measurement_cases'][1]['id'] = value['measurement_cases'][0]['id']
        self.reject(value)
        value = deepcopy(self.manifest)
        value['measurement_cases'][0]['rules'][1]['id'] = 'r0'
        value['measurement_cases'][0]['expected'][1]['rule_id'] = 'r0'
        self.reject(value)

    def test_bad_rule_quantity_and_undeclared_rule_fields_refused(self):
        for mutate in (lambda r: r.update(extra=True), lambda r: r['max_distance'].update(value=True),
                       lambda r: r.update(kind='UNREGISTERED')):
            value = deepcopy(self.manifest)
            mutate(value['measurement_cases'][0]['rules'][0]['input'])
            self.reject(value)

    def test_missing_or_reordered_expected_instance_refused(self):
        value = deepcopy(self.manifest)
        value['measurement_cases'][0]['expected'].pop()
        self.reject(value)
        value = deepcopy(self.manifest)
        value['measurement_cases'][0]['expected'].reverse()
        self.reject(value)

    def test_context_cannot_claim_verified_catalog_or_invalid_geometry(self):
        path = self.root / 'evals/conformance/native.context.json'
        context = json.loads(path.read_bytes())
        roles = set(json.loads((self.root / 'knowledge/registry/pin-types.json').read_bytes())['entries'])
        changes = [lambda c: c.update(verification='AGENT_VERIFIED'),
                   lambda c: c.update(production_bundle_eligible=True), lambda c: c.update(extra=True),
                   lambda c: c['derived_footprints']['simple-pad']['courtyard'].update(min_x=2),
                   lambda c: c['derived_footprints']['simple-pad']['courtyard'].update(min_x=True),
                   lambda c: c['footprint_geometry'].update(A='missing'),
                   lambda c: c['terminal_types'].update({'U1.pin:1': 'GUESSED'})]
        for mutate in changes:
            value = deepcopy(context)
            mutate(value)
            with self.assertRaises(ValueError):
                validate_context(value, roles)

    def test_false_positive_expected_state_is_mismatch_not_acceptance(self):
        manifest, _ = load_manifest(self.root, MANIFEST)
        target = next(c for c in manifest['measurement_cases'] if c['id'] == 'kelvin-disconnected')
        target['expected'][0]['result'] = 'PASS'
        result = run_measurements(self.root, manifest)
        self.assertEqual(result['matched'], 19)
        self.assertEqual(result['status_counts']['FAIL'], 2)
        self.assertNotIn('status', result)

    def test_external_cwd_real_bundle_cli_replay_and_unchanged_inputs(self):
        before = {path: sha(path) for path in self.root.rglob('*')
                  if path.is_file() and '.git' not in path.parts and 'build' not in path.parts}
        bundle_hash = sha(self.bundle)
        process = subprocess.run([sys.executable, str(SCRIPT), '--repo', str(self.root),
                                  '--bundle', str(self.bundle), '--output', 'build/conformance/report.json'],
                                 cwd=self.directory, capture_output=True, text=True, timeout=120)
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout[-1000:])
        value = json.loads(process.stdout)
        self.assertEqual(value['status'], 'MATCH')
        self.assertEqual(value['consumer_replay']['result'], 'FAIL')
        self.assertTrue(value['consumer_replay']['matched'])
        self.assertEqual(value['measurements']['matched'], 20)
        provenance = value['provenance']
        self.assertEqual(provenance['bundle_sha256'], bundle_hash)
        for relative in ('pcbknowledge.workspace.json', 'schemas/envelope.schema.json',
                         'knowledge/registry/pin-types.json', 'knowledge/registry/layout-constraints.json'):
            self.assertEqual(provenance['inputs_sha256'][relative], sha(self.root / relative))
        self.assertEqual(value, json.loads((self.root / 'build/conformance/report.json').read_bytes()))
        self.assertEqual(before, {path: sha(path) for path in before})
        self.assertEqual(bundle_hash, sha(self.bundle))

    def test_cli_requires_explicit_bundle_and_preserves_output_on_invalid_input(self):
        output = self.root / 'build/conformance/preserved.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b'previous receipt')
        value = deepcopy(self.manifest)
        value['measurement_cases'][0]['board']['sha256'] = '0' * 64
        self.path.write_text(json.dumps(value), encoding='utf-8')
        process = subprocess.run([sys.executable, str(SCRIPT), '--repo', str(self.root), '--bundle', str(self.bundle),
                                  '--output', str(output)], cwd=self.directory, capture_output=True, timeout=120)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(output.read_bytes(), b'previous receipt')
        process = subprocess.run([sys.executable, str(SCRIPT), '--repo', str(self.root)],
                                 cwd=self.directory, capture_output=True, timeout=120)
        self.assertEqual(process.returncode, 2)

    def test_output_cannot_replace_bundle_by_direct_dotdot_or_hardlink_alias(self):
        directory = self.root / 'build/output-safety'
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'sub').mkdir(exist_ok=True)
        bundle = directory / 'bundle.json'
        shutil.copyfile(self.bundle, bundle)
        alias = directory / 'hardlink.json'
        before = bundle.read_bytes()
        for destination in (bundle, directory / 'sub/../bundle.json', alias):
            if destination == alias:
                os.link(bundle, alias)
                self.addCleanup(alias.unlink)
            with patch('configs.pcbknowledge_conformance._cli', return_value=None) as execute:
                with self.assertRaises(ValueError):
                    run(self.root, MANIFEST, bundle, destination)
                execute.assert_not_called()
            self.assertEqual(bundle.read_bytes(), before)

    def test_output_cannot_replace_manifest_stored_below_build(self):
        manifest = self.root / 'build/local-manifest.json'
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_bytes(self.original)
        with patch('configs.pcbknowledge_conformance._cli', return_value=None) as execute:
            with self.assertRaises(ValueError):
                run(self.root, 'build/local-manifest.json', self.bundle, manifest)
            execute.assert_not_called()
        self.assertEqual(manifest.read_bytes(), self.original)

    def test_workspace_schema_tamper_refuses_before_vector_validation(self):
        path = self.root / 'schemas/envelope.schema.json'
        before = path.read_bytes()
        self.addCleanup(path.write_bytes, before)
        path.write_bytes(before + b' ')
        with self.assertRaises(RuntimeError):
            load_manifest(self.root, MANIFEST)

    def test_runner_never_imports_test_helpers(self):
        self.assertNotIn('from tests.', SCRIPT.read_text())
        self.assertNotIn('import tests', SCRIPT.read_text())
