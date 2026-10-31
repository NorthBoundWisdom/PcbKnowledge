"""Small committed receipts retain every hash and authenticate recovered local evidence."""
import copy
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from pcbknowledge.serialization import canonical_json, read_json
from pcbknowledge.v2.synthesis_evidence import FIELDS, load_attempt

ROOT = Path(__file__).resolve().parents[2]


class SynthesisEvidenceTests(unittest.TestCase):
    def test_budget_and_all_historical_receipts_and_hashes_are_preserved(self):
        total = sum(p.stat().st_size for p in (ROOT / 'evals').rglob('*') if p.is_file())
        self.assertLess(total, 1_500_000)
        for path in (ROOT / 'evals/synthesis').rglob('*.json'):
            document = read_json(path.read_bytes())
            if not isinstance(document, dict) or 'evidence' not in document:
                continue
            self.assertFalse(set(FIELDS) & set(document))
            raw = subprocess.check_output(['git', 'cat-file', 'blob', document['evidence']['historical_blob']], cwd=ROOT)
            original = read_json(raw)
            self.assertEqual(document['receipt'], original['receipt'])
            self.assertEqual(load_attempt(ROOT, path, recover_history=True)['transcript'], original['transcript'])
            self.assertEqual(document['evidence']['submission_hashes'], [
                {k: v for k, v in submission.items() if k.endswith('sha256')}
                for submission in original['submissions']])

    def test_missing_tampered_or_unsafe_cache_never_passes(self):
        source = ROOT / 'evals/synthesis/g3/one.json'
        document = read_json(source.read_bytes())
        hydrated = load_attempt(ROOT, source, recover_history=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            attempt = root / 'attempt.json'
            attempt.write_text(canonical_json(document))
            with self.assertRaisesRegex(ValueError, 'NOT_LOCALLY_VERIFIED'):
                load_attempt(root, attempt)
            sha = document['evidence']['sha256']
            cache = root / '.pcbknowledge/evals/sha256' / sha[:2] / (sha + '.json')
            cache.parent.mkdir(parents=True)
            evidence = {key: hydrated[key] for key in FIELDS if key in hydrated}
            cache.write_bytes(canonical_json(evidence).encode('utf-8'))
            self.assertEqual(load_attempt(root, attempt)['graph'], document['graph'])
            cache.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                load_attempt(root, attempt)
            cache.unlink()
            cache.symlink_to(attempt)
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                load_attempt(root, attempt)
            mutated = copy.deepcopy(document)
            mutated['evidence']['sha256'] = '../escape'
            attempt.write_text(canonical_json(mutated))
            with self.assertRaisesRegex(ValueError, 'Invalid'):
                load_attempt(root, attempt)

    def test_rehashed_payload_still_checks_original_submission_hash(self):
        source = ROOT / 'evals/synthesis/g3/one.json'
        document = read_json(source.read_bytes())
        hydrated = load_attempt(ROOT, source, recover_history=True)
        evidence = {key: hydrated[key] for key in FIELDS if key in hydrated}
        evidence['submissions'][0]['original_utf8'] += ' '
        payload = canonical_json(evidence)
        sha = hashlib.sha256(payload.encode()).hexdigest()
        document['evidence']['sha256'] = sha
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            attempt = root / 'attempt.json'
            attempt.write_text(canonical_json(document))
            cache = root / '.pcbknowledge/evals/sha256' / sha[:2] / (sha + '.json')
            cache.parent.mkdir(parents=True)
            cache.write_bytes(payload.encode('utf-8'))
            with self.assertRaisesRegex(ValueError, 'submission bytes mismatch'):
                load_attempt(root, attempt)

    def test_malformed_attempts_fail_with_controlled_value_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'attempt.json'
            for document in ([], 'text', {'receipt': []}, {'receipt': {}, 'evidence': []}):
                path.write_bytes(canonical_json(document).encode('utf-8'))
                with self.assertRaises(ValueError):
                    load_attempt(root, path)

    def test_rehashed_output_mutations_cannot_forge_submitted_graph(self):
        source = ROOT / 'evals/synthesis/g3/one.json'
        original = read_json(source.read_bytes())
        hydrated = load_attempt(ROOT, source, recover_history=True)
        for mutation, reason in (('embedded', 'output hash mismatch'), ('final', 'was not submitted')):
            document = copy.deepcopy(original)
            evidence = {key: copy.deepcopy(hydrated[key]) for key in FIELDS if key in hydrated}
            if mutation == 'embedded':
                evidence['submissions'][0]['graph']['id'] = 'forged'
            else:
                document['graph']['id'] = 'forged'
            payload = canonical_json(evidence).encode('utf-8')
            sha = hashlib.sha256(payload).hexdigest()
            document['evidence']['sha256'] = sha
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                path = root / 'attempt.json'
                path.write_bytes(canonical_json(document).encode('utf-8'))
                cache = root / '.pcbknowledge/evals/sha256' / sha[:2] / (sha + '.json')
                cache.parent.mkdir(parents=True)
                cache.write_bytes(payload)
                with self.assertRaisesRegex(ValueError, reason):
                    load_attempt(root, path)
