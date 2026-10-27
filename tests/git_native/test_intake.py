from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pcbknowledge.git_native.intake import (
    INTAKE_FORMAT, MAX_INTAKE_BYTES, IntakeError, load_intake, search_intake,
)


def sample() -> dict:
    return {
        "format": INTAKE_FORMAT, "canonical": False,
        "acceptance_status": "PENDING_USER_REVIEW",
        "sources": [{"id": "source-z", "device": "SYNTH-42",
                     "manufacturer": "Synthetic Maker", "status": "DRAFT"}],
        "facts": [{"id": "fact-b", "source_id": "source-z", "status": "DRAFT",
                   "parameter": "VCC", "value": 3.3},
                  {"id": "fact-a", "source_id": "source-z", "status": "DRAFT",
                   "parameter": "GROUND", "value": 0}],
    }


class IntakeReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.directory = self.root / "knowledge" / "intake"
        self.directory.mkdir(parents=True)

    def write(self, data: dict | None = None, name: str = "synthetic.json") -> Path:
        path = self.directory / name
        path.write_text(json.dumps(sample() if data is None else data), encoding="utf-8")
        return path

    def test_cli_search_is_read_only_and_explicitly_noncanonical(self) -> None:
        import contextlib
        import io
        import subprocess
        from pcbknowledge.git_native.cli import main
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        path = self.write()
        before = path.read_bytes()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["--repo", str(self.root), "intake", "search", "synth-42 VCC"])
        self.assertEqual(result, 0)
        matches = json.loads(output.getvalue())
        self.assertEqual(len(matches), 1)
        self.assertFalse(matches[0]["canonical"])
        self.assertEqual(matches[0]["evidence_verification"], "NOT_LOCALLY_VERIFIED")
        self.assertEqual(path.read_bytes(), before)

    def test_load_is_explicitly_noncanonical_and_does_not_claim_hash_verification(self) -> None:
        self.write()
        (self.directory / "review.md").write_text("Review notes", encoding="utf-8")
        result = load_intake(self.root)
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["canonical"])
        self.assertEqual(result[0]["path"], "knowledge/intake/synthetic.json")
        self.assertEqual(result[0]["evidence_verification"], "NOT_LOCALLY_VERIFIED")
        self.assertEqual(result[0]["data"], sample())

    def test_search_joins_source_keywords_and_is_deterministic(self) -> None:
        self.write()
        self.assertEqual([item["fact"]["id"] for item in search_intake(self.root)],
                         ["fact-a", "fact-b"])
        result = search_intake(self.root, "sYnTh-42 vcc")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source"]["id"], "source-z")
        self.assertEqual(result[0]["fact"]["id"], "fact-b")
        self.assertFalse(result[0]["canonical"])
        self.assertEqual(search_intake(self.root, "missing"), [])

    def test_canonical_records_are_never_loaded_or_mixed(self) -> None:
        canonical = self.root / "knowledge" / "facts"
        canonical.mkdir()
        (canonical / "fact-real.json").write_text("not even valid JSON", encoding="utf-8")
        self.assertEqual(load_intake(self.root), [])
        self.assertEqual(search_intake(self.root), [])
        self.write()
        self.assertEqual(len(search_intake(self.root)), 2)

    def test_false_authority_and_invalid_links_are_rejected(self) -> None:
        for mutate in (
            lambda data: data.update(canonical=True),
            lambda data: data.update(format="canonical-facts"),
            lambda data: data.update(acceptance_status="APPROVED"),
            lambda data: data["facts"][0].update(status="APPROVED"),
            lambda data: data["facts"][0].update(source_id="unknown"),
            lambda data: data["facts"].append(data["facts"][0]),
        ):
            data = sample()
            mutate(data)
            self.write(data)
            with self.assertRaises(IntakeError):
                load_intake(self.root)

    def test_delegated_review_requires_agent_provenance_not_human_claim(self) -> None:
        data = sample()
        data["acceptance_status"] = "AGENT_REVIEWED_UNDER_OWNER_DELEGATION"
        self.write(data)
        with self.assertRaisesRegex(IntakeError, "provenance"):
            load_intake(self.root)
        data["review"] = {"actor_type": "AGENT", "actor_id": "test-agent",
                          "authority": "OWNER_DELEGATION", "outcome": "reviewed",
                          "limitations": ["text locator only"]}
        self.write(data)
        self.assertEqual(len(load_intake(self.root)), 1)
        data["review"]["actor_type"] = "HUMAN"
        self.write(data)
        with self.assertRaisesRegex(IntakeError, "provenance"):
            load_intake(self.root)

    def test_oversize_non_utf8_duplicate_keys_and_nonfinite_rejected(self) -> None:
        path = self.directory / "invalid.json"
        for payload in (b" " * (MAX_INTAKE_BYTES + 1), b"\xff", b'{"canonical":false,"canonical":true}',
                        b'{"value": NaN}'):
            path.write_bytes(payload)
            with self.assertRaises(IntakeError):
                load_intake(self.root)

    def test_symlinks_rejected_without_reading_external_targets(self) -> None:
        target = self.root / "outside.json"
        target.write_text("not JSON", encoding="utf-8")
        try:
            (self.directory / "link.json").symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are unavailable on this platform")
        with self.assertRaisesRegex(IntakeError, "symlink"):
            load_intake(self.root)

    def test_missing_queue_returns_empty(self) -> None:
        self.directory.rmdir()
        self.assertEqual(load_intake(self.root), [])


if __name__ == "__main__":
    unittest.main()
