"""New cache-only receipts never pretend missing evidence was replayed."""
import copy
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from pcbknowledge.serialization import canonical_json
from pcbknowledge.v2.synthesis_cache import FORMAT, import_evidence, validate_descriptor
from pcbknowledge.v2.synthesis_evidence import load_attempt


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def fixture():
    output = {'schema': 'synthetic.graph', 'id': 'original'}
    raw = canonical_json(output)
    hashes = {'original_sha256': hashlib.sha256(raw.encode()).hexdigest(), 'graph_sha256': digest(output)}
    evidence = {'initial_packet': {'task': 'synthetic'}, 'transcript': [],
                'submissions': [{**hashes, 'original_utf8': raw, 'graph': output}]}
    payload = canonical_json(evidence).encode()
    document = {'graph': output, 'receipt': {'format': 'pcbknowledge.synthesis-receipt.v2',
                'graph_sha256': digest(output), 'initial_packet_sha256': digest(evidence['initial_packet']),
                'transcript_sha256': digest(evidence['transcript'])},
                'evidence': {'format': FORMAT, 'bytes': len(payload),
                'sha256': hashlib.sha256(payload).hexdigest(), 'submission_hashes': [hashes]}}
    document['receipt'].update(bundle_commit='0' * 40, bundle_sha256='1' * 64,
                               brief_sha256='2' * 64, skill_sha256='3' * 64,
                               input_identity={'catalog_tree': '4' * 40, 'audit_sha256': '5' * 64,
                                               'engine_sha256': '6' * 64},
                               agent='agent:author', reviewer='agent:reviewer', orchestrator='agent:coordinator',
                               reference_accessed=False, mode='QUERY_MEDIATED', equivalence_review='Synthetic review')
    return document, evidence, payload


class SynthesisCacheTests(unittest.TestCase):
    def setup_repo(self, directory):
        root = Path(directory).resolve()
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        document, evidence, payload = fixture()
        attempt = root / 'attempt.json'
        attempt.write_text(canonical_json(document), encoding='utf-8')
        supplied = root / 'supplied.json'
        supplied.write_bytes(payload)
        subprocess.run(['git', '-C', str(root), 'add', 'attempt.json'], check=True)
        subprocess.run(['git', '-C', str(root), '-c', 'user.name=Synthetic', '-c',
                        'user.email=synthetic@example.invalid', 'commit', '-qm', 'synthetic'], check=True)
        return root, attempt, supplied, document, evidence

    def test_import_and_missing_cache_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root, attempt, supplied, document, evidence = self.setup_repo(directory)
            validate_descriptor(document)
            for recover in (False, True):
                with self.assertRaisesRegex(ValueError, 'NOT_LOCALLY_VERIFIED'):
                    load_attempt(root, attempt, recover_history=recover)
            before = attempt.read_bytes()
            cache = import_evidence(root, attempt, supplied)
            self.assertEqual(load_attempt(root, attempt)['transcript'], evidence['transcript'])
            self.assertEqual(import_evidence(root, attempt, supplied), cache)
            self.assertEqual(attempt.read_bytes(), before)
            cache.write_bytes(b'{}')
            with self.assertRaises(ValueError):
                load_attempt(root, attempt)
            with self.assertRaises(ValueError):
                import_evidence(root, attempt, supplied)

    def test_cli_import_validates_selected_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root, attempt, supplied, _, _ = self.setup_repo(directory)
            from pcbknowledge.workspace import AUTHORITY_DIRECTORIES
            for relative in AUTHORITY_DIRECTORIES:
                (root / relative).mkdir(parents=True)
            software = Path(__file__).resolve().parents[2]
            shutil.copytree(software / 'schemas', root / 'schemas')
            shutil.copyfile(software / '.gitignore', root / '.gitignore')
            shutil.copyfile(software / 'pcbknowledge.workspace.json', root / 'pcbknowledge.workspace.json')
            command = [sys.executable, '-m', 'pcbknowledge.v2.synthesis_cache', '--repo', str(root),
                       '--attempt', str(attempt), '--evidence', str(supplied)]
            process = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn('.pcbknowledge', process.stdout)
            (root / 'pcbknowledge.workspace.json').write_text('{}', encoding='utf-8')
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_alias_above_repository_allowed_but_internal_alias_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            real = base / 'real'
            real.mkdir()
            root, attempt, supplied, _, _ = self.setup_repo(real / 'repo')
            alias = base / 'alias'
            alias.symlink_to(real, target_is_directory=True)
            result = import_evidence(alias / 'repo', alias / 'repo/attempt.json', alias / 'repo/supplied.json')
            self.assertTrue(result.is_relative_to(root))
            inside = root / 'redirect'
            inside.symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symlink|reparse'):
                import_evidence(root, inside / 'attempt.json', supplied)

    def test_git_crlf_checkout_authenticated_without_accepting_whitespace_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root, attempt, supplied, _, _ = self.setup_repo(directory)
            subprocess.run(['git', '-C', str(root), 'config', 'core.autocrlf', 'true'], check=True)
            attempt.unlink()
            subprocess.run(['git', '-C', str(root), 'checkout-index', '-f', 'attempt.json'], check=True)
            self.assertIn(b'\r\n', attempt.read_bytes())
            import_evidence(root, attempt, supplied)
            attempt.write_bytes(attempt.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'committed'):
                import_evidence(root, attempt, supplied)

    def test_strict_metadata(self):
        original, _, _ = fixture()
        mutations = [('version', lambda d: d['evidence'].update(format='unknown')),
                     ('history', lambda d: d['evidence'].update(historical_blob='0' * 40)),
                     ('size', lambda d: d['evidence'].update(bytes=True)),
                     ('digest', lambda d: d['evidence'].update(sha256='../escape')),
                     ('submissions', lambda d: d['evidence'].update(submission_hashes=[])),
                     ('receipt', lambda d: d.pop('receipt')),
                     ('review-type', lambda d: d['receipt'].update(equivalence_review={})),
                     ('review-blank', lambda d: d['receipt'].update(equivalence_review='  ')),
                     ('packet', lambda d: d['receipt'].pop('initial_packet_sha256')),
                     ('final', lambda d: d['graph'].update(id='forged'))]
        for name, mutate in mutations:
            document = copy.deepcopy(original)
            mutate(document)
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_descriptor(document)

    def test_import_rejects_uncommitted_descriptor_and_tampered_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root, attempt, supplied, document, _ = self.setup_repo(directory)
            original = attempt.read_bytes()
            attempt.write_bytes(original + b' ')
            with self.assertRaisesRegex(ValueError, 'committed'):
                import_evidence(root, attempt, supplied)
            attempt.write_bytes(original)
            supplied.write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError, 'size or SHA'):
                import_evidence(root, attempt, supplied)
            self.assertFalse((root / '.pcbknowledge').exists())

    def test_rehashed_packet_transcript_and_submission_tampering_refused(self):
        from pcbknowledge.v2.synthesis_cache import validate_payload
        for field in ('initial_packet', 'transcript', 'submissions'):
            document, evidence, _ = fixture()
            if field == 'submissions':
                evidence[field][0]['original_utf8'] += ' '
            else:
                evidence[field] = {'forged': True}
            payload = canonical_json(evidence).encode()
            document['evidence'].update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_payload(document, payload)

    def test_symlink_cache_parent_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root, attempt, supplied, _, _ = self.setup_repo(directory)
            other = root / 'other'
            other.mkdir()
            (root / '.pcbknowledge').symlink_to(other, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                import_evidence(root, attempt, supplied)
            self.assertEqual(list(other.iterdir()), [])
