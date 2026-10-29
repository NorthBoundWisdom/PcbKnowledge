"""Selection drift is broader than individual item metadata drift."""
from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
from unittest import mock

from pcbknowledge.git_native.cli import main
from pcbknowledge.git_native.intake import IntakeError, load_intake
from pcbknowledge.git_native.intake_bundle import intake_bundle, verify_intake_bundle, StaleIntakeBundle
from pcbknowledge.git_native.intake_reference import resolve_intake_reference
from tests.git_native.support import RepositoryTestCase
from tests.git_native.test_intake_dispositions import synthetic_batch, synthetic_disposition


class IntakeBundleVerificationTests(RepositoryTestCase):
    def setUp(self):
        super().setUp()
        self.path = self.root / 'knowledge/intake/synthetic.json'
        self.path.parent.mkdir()
        self.data = synthetic_batch()
        self.write()
        self.captured = intake_bundle(self.root, device='SYNTH-A')

    def write(self, data=None, path=None):
        (path or self.path).write_text(json.dumps(self.data if data is None else data), encoding='utf-8')

    def verify(self, digest=None, **filters):
        return verify_intake_bundle(self.root, expected_sha256=digest or self.captured['bundle_sha256'],
                                    **(filters or {'device': 'SYNTH-A'}))

    def invoke(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                code = main(['--repo', str(self.root), 'intake', 'verify-bundle', *arguments])
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def test_success_wraps_identical_capture_without_relabeling_its_hash(self):
        result = self.verify()
        self.assertEqual(result['bundle'], self.captured)
        self.assertEqual(result['expected_sha256'], self.captured['bundle_sha256'])
        self.assertEqual(result['operation'], 'VERIFY_CURRENT_METADATA_SELECTION')
        self.assertEqual(result['bundle']['operation'], 'CAPTURE_CURRENT_METADATA')
        self.assertFalse(result['canonical'])
        self.assertEqual(result['evidence_verification'], 'NOT_LOCALLY_VERIFIED')
        self.assertEqual(result, self.verify())

    def test_new_matching_batch_invalidates_selection_not_old_item_pins(self):
        self.write(self.data, self.path.parent / 'new.json')
        for record in self.captured['batches'][0]['facts'] + self.captured['batches'][0]['issues']:
            self.assertEqual(resolve_intake_reference(self.root, {k: [v] for k, v in record['reference'].items()}).candidate,
                             record['candidate'])
        with self.assertRaises(StaleIntakeBundle):
            self.verify()
        self.path.unlink()
        with self.assertRaises(StaleIntakeBundle):
            self.verify()

    def test_fact_issue_source_and_batch_context_mutations_are_detected(self):
        mutations = [lambda d: d['facts'].append({'id': 'added', 'source_id': 'source-a', 'status': 'DRAFT'}),
                     lambda d: d['facts'].pop(0),
                     lambda d: d['source_issues'].append({'id': 'added', 'source_id': 'source-a'}),
                     lambda d: d['source_issues'].clear(),
                     lambda d: d['sources'].append({'id': 'added', 'device': 'SYNTH-A', 'status': 'DRAFT'}),
                     lambda d: d['sources'][0].update(revision='SYNTH-R2'),
                     lambda d: d.update(limitations=['New unknown']),
                     lambda d: d['facts'][0].update(conditions={'unknown': None})]
        for change in mutations:
            changed = copy.deepcopy(self.data)
            change(changed)
            self.write(changed)
            with self.subTest(change=change), self.assertRaises(StaleIntakeBundle):
                self.verify()
        self.write()
        self.assertEqual(self.verify()['bundle'], self.captured)

    def test_last_matching_source_removal_and_entire_batch_removal_detected(self):
        self.data['sources'][0]['device'] = 'NOT-SELECTED'
        self.write()
        with self.assertRaises(StaleIntakeBundle):
            self.verify()
        self.path.unlink()
        with self.assertRaises(StaleIntakeBundle):
            self.verify()

    def test_unmatched_new_batch_does_not_change_selected_bundle(self):
        other = synthetic_batch()
        other['sources'][0]['device'] = 'OTHER'
        self.write(other, self.path.parent / 'other.json')
        self.assertEqual(self.verify()['bundle'], self.captured)
        # Whole-queue validation still applies, even outside selected scope.
        (self.path.parent / 'other.json').write_text('invalid', encoding='utf-8')
        with self.assertRaises(IntakeError):
            self.verify()

    def test_empty_to_nonempty_selection_is_detected(self):
        empty = intake_bundle(self.root, device='MISSING')
        self.assertEqual(self.verify(empty['bundle_sha256'], device='MISSING')['bundle'], empty)
        self.data['sources'][0]['device'] = 'MISSING'
        self.write()
        with self.assertRaises(StaleIntakeBundle):
            self.verify(empty['bundle_sha256'], device='MISSING')

    def test_filters_bound_even_when_they_select_identical_records(self):
        with self.assertRaises(StaleIntakeBundle):
            self.verify(source_id='source-a')
        with self.assertRaises(StaleIntakeBundle):
            self.verify(device='SYNTH-A', revision='SYNTH-R')
        with self.assertRaises(StaleIntakeBundle):
            self.verify(device='synth-a')
        with self.assertRaises(StaleIntakeBundle):
            self.verify(device=' SYNTH-A')

    def test_byte_only_and_disposition_only_changes_are_detected(self):
        self.path.write_bytes(self.path.read_bytes() + b'\n')
        with self.assertRaises(StaleIntakeBundle):
            self.verify()
        self.write()
        receipt = synthetic_disposition(self.path, self.path.relative_to(self.root).as_posix())
        path = self.root / 'knowledge/intake-dispositions/synthetic.json'
        path.parent.mkdir()
        path.write_text(json.dumps(receipt), encoding='utf-8')
        with self.assertRaises(StaleIntakeBundle):
            self.verify()
        current = intake_bundle(self.root, device='SYNTH-A')['bundle_sha256']
        receipt['summary'] = 'Changed synthetic context.'
        path.write_text(json.dumps(receipt), encoding='utf-8')
        with self.assertRaises(StaleIntakeBundle):
            self.verify(current)

    def test_one_load_and_no_post_validation_refresh(self):
        batches = load_intake(self.root)
        def loaded(_):
            self.path.write_bytes(self.path.read_bytes() + b'\n')
            return batches
        with mock.patch('pcbknowledge.git_native.intake_bundle.load_intake', side_effect=loaded) as loader:
            self.assertEqual(self.verify()['bundle'], self.captured)
        self.assertEqual(loader.call_count, 1)
        with self.assertRaises(StaleIntakeBundle):
            self.verify()

    def test_digest_validation_precedes_loader_and_cli_rejects_ambiguous_options(self):
        for digest in (None, 1, '', 'A' * 64, '0' * 63, '0' * 65, 'g' * 64, '0' * 64 + '\n'):
            with mock.patch('pcbknowledge.git_native.intake_bundle.load_intake') as loader:
                with self.assertRaises(IntakeError):
                    verify_intake_bundle(self.root, expected_sha256=digest, device='SYNTH-A')
                loader.assert_not_called()
        valid = ['--device', 'SYNTH-A', '--sha256', self.captured['bundle_sha256']]
        for args in ([], ['--device', 'SYNTH-A'], ['--sha256', '0' * 64],
                     valid + ['--sha256', '0' * 64], valid + ['--device', 'SYNTH-A'],
                     valid + ['--kind', 'x'], ['--dev', 'SYNTH-A', '--sha256', '0' * 64]):
            code, output, _ = self.invoke(*args)
            self.assertEqual(code, 2, args)
            self.assertEqual(output, '')

    def test_stale_cli_has_named_error_and_no_new_digest_or_partial_payload(self):
        code, output, errors = self.invoke('--device', 'SYNTH-A', '--sha256', '0' * 64)
        self.assertEqual(code, 2)
        self.assertEqual(output, '')
        self.assertIn('STALE_INTAKE_BUNDLE', errors)
        self.assertNotIn(self.captured['bundle_sha256'], errors)
        code, output, errors = self.invoke('--device', 'SYNTH-A', '--sha256', self.captured['bundle_sha256'])
        self.assertEqual(code, 0, errors)
        self.assertEqual(json.loads(output), self.verify())

    def test_public_entrypoint_reads_only_selected_workspace_success_and_failure(self):
        script = Path(__file__).resolve().parents[2] / 'configs/pcbknowledge_agent.py'
        shutil.rmtree(self.root / '.pcbknowledge')
        def snapshot():
            return {str(p.relative_to(self.root)): p.read_bytes() if p.is_file() else None
                    for p in self.root.rglob('*')}
        command = [sys.executable, '-B', str(script), '--repo', str(self.root), 'intake',
                   'verify-bundle', '--device', 'SYNTH-A', '--sha256', self.captured['bundle_sha256']]
        before = snapshot()
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), self.verify())
        self.assertEqual(snapshot(), before)
        self.write(self.data, self.path.parent / 'new.json')
        before = snapshot()
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertIn('STALE_INTAKE_BUNDLE', result.stderr)
        self.assertEqual(snapshot(), before)
