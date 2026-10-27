from __future__ import annotations

import json
import subprocess
from dataclasses import replace

from pcbknowledge.git_native.model import EntityRecord, PreparedBy
from pcbknowledge.git_native.pilot_eval import PilotEvaluationManifest, build_pilot_report
from pcbknowledge.git_native.snapshot import snapshot_fingerprint
from tests.git_native.support import RepositoryTestCase


class SnapshotEqualityTests(RepositoryTestCase):
    def _commit(self) -> str:
        subprocess.run(["git", "add", "knowledge"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
             "commit", "-qm", "synthetic authority"],
            cwd=self.root, check=True,
        )
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.root, text=True,
        ).strip()

    def _manufacturer(self, name: str, key: str):
        return self.repository.create_manufacturer(
            name, prepared_by=PreparedBy.AGENT, idempotency_key=key,
        )

    def _gate(self, ref: str = "HEAD"):
        report = build_pilot_report(
            self.repository, PilotEvaluationManifest("synthetic", (), ()),
            published_ref=ref,
        )
        return next(g for g in report.gates if g.name == "published-matches-working")

    def test_same_counts_and_ids_with_changed_content_fail(self) -> None:
        original = self._manufacturer("Synthetic Maker", "maker")
        self._commit()
        self.assertTrue(self._gate().passed)
        changed = EntityRecord.manufacturer(
            original.id, "Different Synthetic Maker", prepared_by=PreparedBy.AGENT,
        )
        self.repository.entity_path(original.id).write_text(changed.canonical_json())
        self.assertFalse(self._gate().passed)

    def test_replacement_ids_with_same_counts_fail(self) -> None:
        original = self._manufacturer("Synthetic Maker", "maker")
        self._commit()
        self.repository.entity_path(original.id).unlink()
        replacement = self._manufacturer("Synthetic Maker", "replacement")
        self.assertNotEqual(original.id, replacement.id)
        self.assertFalse(self._gate().passed)

    def test_comparison_uses_selected_published_ref(self) -> None:
        self._manufacturer("Synthetic Maker", "maker")
        original_commit = self._commit()
        subprocess.run(["git", "tag", "synthetic-original"], cwd=self.root, check=True)
        self._manufacturer("Second Synthetic Maker", "maker-two")
        self._commit()
        self.assertTrue(self._gate().passed)
        self.assertFalse(self._gate("synthetic-original").passed)
        report = build_pilot_report(
            self.repository, PilotEvaluationManifest("synthetic", (), ()),
            published_ref="synthetic-original",
        )
        self.assertEqual(report.published_commit, original_commit)

    def test_order_and_json_formatting_do_not_change_content_identity(self) -> None:
        self._manufacturer("Synthetic Maker", "maker")
        self._manufacturer("Second Synthetic Maker", "maker-two")
        snapshot = self.repository.validate_all(require_canonical=True)
        reversed_snapshot = replace(snapshot, entities=tuple(reversed(snapshot.entities)))
        self.assertEqual(snapshot_fingerprint(snapshot), snapshot_fingerprint(reversed_snapshot))
        # Parsing equivalent JSON has the same logical fingerprint. Repository
        # publication still separately enforces canonical bytes; do not relax it.
        reformatted = tuple(
            EntityRecord.from_json(json.dumps(entity.to_dict(), indent=4, sort_keys=True))
            for entity in snapshot.entities
        )
        self.assertEqual(
            snapshot_fingerprint(snapshot),
            snapshot_fingerprint(replace(snapshot, entities=reformatted)),
        )
        self._commit()
        self.assertTrue(self._gate().passed)

    def test_derived_snapshot_metadata_is_not_canonical_content(self) -> None:
        self._manufacturer("Synthetic Maker", "maker")
        snapshot = self.repository.validate_all(require_canonical=True)
        changed_metadata = replace(
            snapshot, ref="another-ref", commit="a" * 40,
            local_evidence_verification=(("pk_" + "a" * 24, "NOT_LOCALLY_VERIFIED"),),
        )
        self.assertEqual(snapshot_fingerprint(snapshot), snapshot_fingerprint(changed_metadata))
