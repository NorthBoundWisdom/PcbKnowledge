"""Content identities for synthesis inputs and the executing Python engine."""
from __future__ import annotations

import hashlib
from pathlib import Path

from pcbknowledge.serialization import canonical_json

RECEIPT_FORMAT = 'pcbknowledge.synthesis-receipt.v2'


def is_digest(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(character in '0123456789abcdef' for character in value))


def engine_digest():
    """Hash installed runtime sources, including dirty edits, independently of Git metadata."""
    root = Path(__file__).resolve().parents[1]
    files = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(root.rglob('*.py'))}
    return hashlib.sha256(canonical_json(files).encode('utf-8')).hexdigest()


def input_identity(bundle):
    return {'catalog_tree': bundle.catalog_tree, 'audit_sha256': bundle.audit_sha256,
            'engine_sha256': engine_digest()}


def validate_identity(identity):
    if (not isinstance(identity, dict) or set(identity) != {'catalog_tree', 'audit_sha256', 'engine_sha256'}
            or not is_digest(identity['catalog_tree'], 40)
            or any(not is_digest(identity[key], 64) for key in ('audit_sha256', 'engine_sha256'))):
        raise ValueError('Invalid synthesis content identity')


def match_identity(bundle, identity, *, replay=False):
    validate_identity(identity)
    actual = input_identity(bundle)
    fields = ('catalog_tree', 'audit_sha256') if replay else tuple(actual)
    if any(identity[key] != actual[key] for key in fields):
        raise ValueError('Synthesis catalog or executing engine identity mismatch (including audit inputs)')
    return actual


def receipt_identity(bundle, receipt, *, replay=False):
    if receipt.get('format') != RECEIPT_FORMAT:
        raise ValueError('Current synthesis requires a content-identified v2 receipt')
    identity = receipt.get('input_identity')
    match_identity(bundle, identity, replay=replay)
    if not is_digest(receipt.get('bundle_commit'), 40) or not is_digest(receipt.get('bundle_sha256'), 64):
        raise ValueError('Invalid original bundle provenance')
    return identity
