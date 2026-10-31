"""Content-addressed local synthesis evidence and authenticated historical recovery."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess

from pcbknowledge.serialization import canonical_json, read_json

FIELDS = ('initial_packet', 'submissions', 'transcript', 'author_reports')
LIMIT = 8 * 1024 * 1024


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _hex(value, length):
    return isinstance(value, str) and len(value) == length and all(c in '0123456789abcdef' for c in value)


def _validate(document, evidence):
    receipt = document['receipt']
    if not isinstance(evidence, dict) or any(key not in evidence for key in FIELDS[:3]):
        raise ValueError('Malformed synthesis evidence object')
    submissions = evidence['submissions']
    hashes = document['evidence'].get('submission_hashes')
    if not isinstance(submissions, list) or not isinstance(hashes, list):
        raise ValueError('Malformed synthesis submission list')
    if any(not isinstance(row, dict) for row in submissions + hashes):
        raise ValueError('Malformed synthesis submission object')
    for key in ('initial_packet', 'transcript'):
        if _sha(canonical_json(evidence[key]).encode()) != receipt.get(key + '_sha256'):
            raise ValueError('Synthesis evidence does not match receipt: ' + key)
    if not evidence.get('submissions'):
        raise ValueError('Missing original synthesis submissions')
    outputs = []
    for submission, hashes in zip(evidence['submissions'], document['evidence']['submission_hashes'], strict=True):
        if {k: v for k, v in submission.items() if k.endswith('sha256')} != hashes:
            raise ValueError('Synthesis submission receipt mismatch')
        if not isinstance(submission.get('original_utf8'), str):
            raise ValueError('Malformed synthesis submission text')
        raw = submission['original_utf8'].encode()
        expected = hashes.get('original_sha256', hashes.get('raw_sha256'))
        if _sha(raw) != expected:
            raise ValueError('Synthesis submission bytes mismatch')
        output = read_json(raw)
        outputs.append(output)
        for key in ('graph', 'refusal'):
            if key + '_sha256' in hashes:
                if submission.get(key) != output or _sha(canonical_json(output).encode()) != hashes[key + '_sha256']:
                    raise ValueError('Synthesis submitted output hash mismatch')
    if document.get('graph', document.get('refusal')) not in outputs:
        raise ValueError('Final synthesis output was not submitted')


def load_attempt(root, path, *, recover_history=False):
    """Read a receipt and verify local bytes; history recovery is explicit and read-only."""
    root, path = Path(root).resolve(), Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > LIMIT:
        raise ValueError('Unsafe or oversized synthesis attempt')
    document = read_json(path.read_bytes())
    if not isinstance(document, dict) or not isinstance(document.get('receipt'), dict):
        raise ValueError('Malformed synthesis attempt object')
    descriptor = document.get('evidence')
    if descriptor is None:
        return document
    if not isinstance(descriptor, dict):
        raise ValueError('Malformed synthesis evidence descriptor')
    cache_only = 'format' in descriptor
    if cache_only:
        from .synthesis_cache import validate_descriptor
        validate_descriptor(document)
    expected = descriptor.get('sha256')
    if not _hex(expected, 64):
        raise ValueError('Invalid synthesis evidence digest')
    cache = root / '.pcbknowledge/evals/sha256' / expected[:2] / (expected + '.json')
    if cache.resolve() != cache or cache.is_symlink():
        raise ValueError('Unsafe synthesis evidence cache path')
    if cache.exists():
        if not cache.is_file() or cache.stat().st_size > LIMIT:
            raise ValueError('Oversized synthesis evidence')
        payload = cache.read_bytes()
    elif recover_history and not cache_only:
        blob = descriptor.get('historical_blob')
        if not _hex(blob, 40):
            raise ValueError('No authenticated historical evidence blob')
        process = subprocess.run(['git', '-C', str(root), 'cat-file', 'blob', blob], capture_output=True)
        if process.returncode or len(process.stdout) > LIMIT:
            raise ValueError('Historical synthesis evidence unavailable; fetch full history')
        original = read_json(process.stdout)
        if not isinstance(original, dict):
            raise ValueError('Malformed historical synthesis attempt')
        for key, value in document.items():
            if key != 'evidence' and original.get(key) != value:
                raise ValueError('Historical synthesis receipt or output mismatch')
        payload = canonical_json({key: original[key] for key in FIELDS if key in original}).encode()
    else:
        raise ValueError('NOT_LOCALLY_VERIFIED: missing synthesis evidence ' + expected)
    if cache_only:
        from .synthesis_cache import validate_payload
        return {**document, **validate_payload(document, payload)}
    if _sha(payload) != expected:
        raise ValueError('Synthesis evidence SHA-256 mismatch')
    evidence = read_json(payload)
    if not isinstance(evidence, dict) or set(evidence) - set(FIELDS):
        raise ValueError('Unexpected synthesis evidence fields')
    _validate(document, evidence)
    return {**document, **evidence}
