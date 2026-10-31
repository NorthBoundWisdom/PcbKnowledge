"""Strict metadata and explicit local import for new cache-only synthesis attempts."""
import argparse
import hashlib
from pathlib import Path
import subprocess

from pcbknowledge.serialization import canonical_json, read_json
from .synthesis_evidence import FIELDS, LIMIT, _hex, _validate

FORMAT = 'pcbknowledge.synthesis-cache.v1'


def _receipt_metadata(receipt):
    from .synthesis_identity import validate_identity
    if not isinstance(receipt, dict) or receipt.get('format') != 'pcbknowledge.synthesis-receipt.v2':
        raise ValueError('Missing synthesis receipt')
    validate_identity(receipt.get('input_identity'))
    for key, size in (('bundle_commit', 40), ('bundle_sha256', 64), ('brief_sha256', 64),
                      ('skill_sha256', 64), ('initial_packet_sha256', 64), ('transcript_sha256', 64)):
        if not _hex(receipt.get(key), size):
            raise ValueError('Missing synthesis receipt hash: ' + key)
    actors = [receipt.get(key) for key in ('agent', 'reviewer', 'orchestrator')]
    if any(not isinstance(actor, str) or not actor.startswith('agent:') for actor in actors):
        raise ValueError('Missing synthesis receipt actors')
    if len(set(actors)) != 3 or receipt.get('reference_accessed') is not False:
        raise ValueError('Invalid synthesis independence metadata')
    review = receipt.get('equivalence_review')
    if receipt.get('mode') != 'QUERY_MEDIATED' or not isinstance(review, str) or not review.strip():
        raise ValueError('Missing synthesis mode or independent review')


def validate_descriptor(document):
    """Audit metadata only; this never authenticates absent packet/transcript bytes."""
    if not isinstance(document, dict):
        raise ValueError('Malformed synthesis attempt')
    descriptor = document.get('evidence')
    receipt = document.get('receipt')
    keys = {'format', 'bytes', 'sha256', 'submission_hashes'}
    if not isinstance(descriptor, dict) or set(descriptor) != keys or descriptor['format'] != FORMAT:
        raise ValueError('Invalid cache-only synthesis descriptor')
    size = descriptor['bytes']
    if type(size) is not int or not 0 < size <= LIMIT or not _hex(descriptor['sha256'], 64):
        raise ValueError('Invalid cache-only synthesis size or digest')
    _receipt_metadata(receipt)
    hashes = descriptor['submission_hashes']
    if not isinstance(hashes, list) or not hashes:
        raise ValueError('Missing synthesis submission hashes')
    for row in hashes:
        if not isinstance(row, dict) or not row or any(not _hex(v, 64) for v in row.values()):
            raise ValueError('Invalid synthesis submission hash')
        if set(row) not in ({'original_sha256', 'graph_sha256'}, {'original_sha256', 'refusal_sha256'},
                            {'raw_sha256', 'graph_sha256'}, {'raw_sha256', 'refusal_sha256'}):
            raise ValueError('Invalid synthesis submission hash fields')
    outputs = [key for key in ('graph', 'refusal') if key in document]
    if (len(outputs) != 1 or not isinstance(document[outputs[0]], dict)
            or set(FIELDS) & set(document)):
        raise ValueError('Cache-only attempt must retain exactly one final output, not evidence bytes')
    key = outputs[0] + '_sha256'
    digest = hashlib.sha256(canonical_json(document[outputs[0]]).encode()).hexdigest()
    if receipt.get(key) != digest or not any(row.get(key) == digest for row in hashes):
        raise ValueError('Final output differs from receipt or submission hashes')
    return descriptor


def validate_payload(document, payload):
    descriptor = validate_descriptor(document)
    if len(payload) != descriptor['bytes'] or hashlib.sha256(payload).hexdigest() != descriptor['sha256']:
        raise ValueError('Synthesis evidence size or SHA-256 mismatch')
    evidence = read_json(payload)
    if not isinstance(evidence, dict) or set(evidence) - set(FIELDS):
        raise ValueError('Unexpected synthesis evidence fields')
    _validate(document, evidence)
    return evidence


def import_evidence(root, attempt, supplied):
    """Import authenticated bytes only; never change the committed descriptor or receipt."""
    from .derived_paths import repository_boundary, repository_path
    selected = Path(root).absolute()
    attempt = repository_path(selected, attempt)
    root = selected.resolve()
    supplied = Path(supplied).absolute()
    if repository_boundary(selected, supplied) is not None:
        supplied = repository_path(selected, supplied)
    relative = attempt.relative_to(root).as_posix()
    process = subprocess.run(['git', '-C', str(root), 'show', 'HEAD:' + relative], capture_output=True)
    if attempt.stat().st_size > LIMIT:
        raise ValueError('Oversized synthesis attempt')
    actual = subprocess.run(['git', '-C', str(root), 'hash-object', '--path=' + relative, str(attempt)],
                            capture_output=True)
    expected = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD:' + relative], capture_output=True)
    if (process.returncode or actual.returncode or expected.returncode or len(process.stdout) > LIMIT
            or actual.stdout.strip() != expected.stdout.strip()):
        raise ValueError('Attempt must match the committed HEAD descriptor through Git checkout conversion')
    document = read_json(process.stdout)
    if not isinstance(document, dict):
        raise ValueError('Malformed synthesis attempt')
    if supplied.is_symlink() or supplied.resolve() != supplied or not supplied.is_file():
        raise ValueError('Unsafe supplied synthesis evidence')
    if supplied.stat().st_size > LIMIT:
        raise ValueError('Oversized supplied synthesis evidence')
    payload = supplied.read_bytes()
    validate_payload(document, payload)
    digest = document['evidence']['sha256']
    cache = root / '.pcbknowledge/evals/sha256' / digest[:2] / (digest + '.json')
    try:
        cache = repository_path(selected, cache)
    except ValueError as error:
        raise ValueError('Unsafe synthesis evidence cache path') from error
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists():
        if not cache.is_file() or cache.stat().st_size > LIMIT or cache.read_bytes() != payload:
            raise ValueError('Existing synthesis cache differs from supplied evidence')
    else:
        with cache.open('xb') as stream:
            stream.write(payload)
    return cache


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    arguments = parser.parse_args()
    from pcbknowledge.workspace import validate_workspace
    validate_workspace(arguments.repo)
    print(import_evidence(arguments.repo, arguments.attempt, arguments.evidence))


if __name__ == '__main__':
    main()
