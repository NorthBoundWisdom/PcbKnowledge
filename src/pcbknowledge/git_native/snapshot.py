"""Canonical authority content identity shared by pilot gates and receipts.

Only current Source, Entity and Fact canonical fields participate. Snapshot refs,
commit IDs, derived conflicts and local evidence-cache availability are not record
content. Keep the byte framing stable so existing scenario fingerprints retain
exactly the same meaning.
"""

from __future__ import annotations

import hashlib

from pcbknowledge.git_native.store import AuthoritySnapshot


def snapshot_fingerprint(snapshot: AuthoritySnapshot) -> str:
    digest = hashlib.sha256()
    for prefix, records in (
        ("SOURCE", snapshot.sources),
        ("ENTITY", snapshot.entities),
        ("FACT", snapshot.facts),
    ):
        for record in sorted(records, key=lambda item: item.id):
            digest.update(prefix.encode("ascii"))
            digest.update(b"\0")
            digest.update(record.id.encode("ascii"))
            digest.update(b"\0")
            digest.update(record.canonical_json().encode("utf-8"))
    return digest.hexdigest()
