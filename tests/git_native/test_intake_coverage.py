"""Synthetic inventory tests: counts never certify evidence or components."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from configs import pcbknowledge_agent
from pcbknowledge.git_native.cli import main
from pcbknowledge.git_native.intake import IntakeError
from pcbknowledge.git_native.intake_coverage import intake_coverage
from pcbknowledge.git_native.workspace import initialize_workspace
from tests.git_native.test_intake_dispositions import synthetic_batch, synthetic_disposition


def fixture() -> dict:
    data = synthetic_batch()
    data["sources"][0]["manufacturer"] = "Synthetic Maker"
    data["sources"][1]["manufacturer"] = "Synthetic Maker"
    data["review"] = {"actor_type": "AGENT", "actor_id": "agent:synthetic",
                      "authority": "OWNER_DELEGATION"}
    data["limitations"] = ["Synthetic missing inputs; not engineering knowledge."]
    data["facts"][0].update(kind="pin", evidence={
        "evidence_level": "SYNTHETIC_TEXT_ONLY", "visual_checked": False,
        "reviewer": "agent:synthetic-evidence", "collector": "agent:synthetic-collector"})
    data["facts"][1].update(kind="pin", evidence={"visual_page_review": True})
    return data


class IntakeCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.directory = self.root / "knowledge/intake"
        self.directory.mkdir(parents=True)

    def write(self, data: dict | None = None, name: str = "synthetic.json") -> Path:
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fixture() if data is None else data), encoding="utf-8")
        return path

    def tree(self) -> dict:
        return {path.relative_to(self.root).as_posix(): None if path.is_dir() else path.read_bytes()
                for path in self.root.rglob("*")}

    def test_empty_queue_has_no_inferred_scope_or_authority(self) -> None:
        result = intake_coverage(self.root)
        self.assertEqual(result["summary"]["batch_count"], 0)
        self.assertEqual(result["summary"]["recorded_metadata"]["record_count"], 0)
        self.assertEqual(result["device_labels"], [])
        self.assertEqual(result["batches"], [])
        self.assertFalse(result["canonical"])
        self.assertEqual(result["evidence_verification"], "NOT_LOCALLY_VERIFIED")
        self.assertTrue(any("Owner acceptance is not inferred" in line for line in result["limitations"]))

    def test_batch_local_sources_and_ids_are_not_deduplicated_by_label_or_hash(self) -> None:
        self.write(name="b.json")
        self.write(name="a.json")
        result = intake_coverage(self.root)
        summary = result["summary"]
        self.assertEqual(summary["batch_count"], 2)
        self.assertEqual(summary["batch_local_source_scope_count"], 4)
        self.assertEqual(summary["recorded_metadata"]["record_count"], 4)
        self.assertEqual(summary["distinct_device_label_count"], 2)
        self.assertEqual([item["path"] for item in result["batches"]],
                         ["knowledge/intake/a.json", "knowledge/intake/b.json"])
        self.assertEqual(result["device_labels"][0]["source_scopes"], [
            {"path": "knowledge/intake/a.json", "source_id": "source-a"},
            {"path": "knowledge/intake/b.json", "source_id": "source-a"}])

    def test_raw_recorded_evidence_flags_and_provenance_are_not_upgraded(self) -> None:
        data = fixture()
        data["acceptance_status"] = "AGENT_REVIEWED_UNDER_OWNER_DELEGATION"
        data["facts"][1]["status"] = "AGENT_REVIEWED_UNDER_OWNER_DELEGATION"
        self.write(data)
        result = intake_coverage(self.root)
        metadata = result["summary"]["recorded_metadata"]
        self.assertEqual(metadata["record_statuses"], [
            {"value": "AGENT_REVIEWED_UNDER_OWNER_DELEGATION", "count": 1},
            {"value": "DRAFT", "count": 1}])
        self.assertEqual(metadata["evidence_levels"], [
            {"value": "SYNTHETIC_TEXT_ONLY", "count": 1}, {"value": None, "count": 1}])
        self.assertEqual(metadata["visual_checked"], [
            {"value": False, "count": 1}, {"value": None, "count": 1}])
        self.assertEqual(metadata["visual_page_review"], [
            {"value": None, "count": 1}, {"value": True, "count": 1}])
        batch = result["batches"][0]
        self.assertEqual(batch["review"], data["review"])
        self.assertEqual(batch["limitations"], data["limitations"])
        self.assertEqual(batch["sources"][0]["source"], data["sources"][0])
        self.assertEqual(batch["sources"][0]["recorded_metadata"]["evidence_reviewers"],
                         [{"value": "agent:synthetic-evidence", "count": 1}])

    def test_missing_and_nonstring_metadata_stay_unknown_without_prose_inference(self) -> None:
        data = fixture()
        data["sources"][0].update(manufacturer=None, scope="Synthetic Maker SYNTH-A package P")
        data["sources"][1]["device"] = ["SYNTH-B"]
        data["facts"][0].update(kind=["pin"], evidence="not an evidence object")
        data["facts"][1]["evidence"] = {"evidence_level": {"untyped": True}}
        self.write(data)
        result = intake_coverage(self.root)
        self.assertEqual(result["device_labels"], [])
        summary = result["summary"]
        self.assertEqual(summary["source_scopes_without_device_labels"], 2)
        metadata = summary["recorded_metadata"]
        self.assertEqual(metadata["evidence_missing_or_nonobject_count"], 1)
        self.assertIn({"value": ["pin"], "count": 1}, metadata["fact_kinds"])
        self.assertIn({"value": {"untyped": True}, "count": 1}, metadata["evidence_levels"])

    def test_device_labels_preserve_case_unicode_and_whitespace(self) -> None:
        for index, label in enumerate(("SYNTH-A", "synth-a", "SYNTH-A ", "SYNTH-\u212a", "SYNTH-K")):
            data = fixture()
            data["sources"][0]["device"] = label
            self.write(data, f"{index}.json")
        result = intake_coverage(self.root)
        self.assertEqual(result["summary"]["distinct_device_label_count"], 6)

    def test_sorted_projection_retains_exact_byte_fingerprint(self) -> None:
        data = fixture()
        data["source_issues"].append({"id": "z-gap", "source_id": "source-a",
                                     "issue_status": "UNRESOLVED_APPLICATION_INPUTS"})
        self.write(data)
        first = intake_coverage(self.root)
        data["sources"].reverse()
        data["facts"].reverse()
        data["source_issues"].reverse()
        self.write(data)
        second = intake_coverage(self.root)
        self.assertEqual(second, intake_coverage(self.root))
        self.assertNotEqual(first["batches"][0].pop("sha256"), second["batches"][0].pop("sha256"))
        self.assertEqual(first, second)

    def add_disposition(self) -> tuple[Path, dict]:
        path = self.write()
        data = synthetic_disposition(path, path.relative_to(self.root).as_posix())
        target = self.root / "knowledge/intake-dispositions/synthetic.json"
        target.parent.mkdir()
        target.write_text(json.dumps(data), encoding="utf-8")
        return target, data

    def test_containment_is_not_resolution_and_never_leaks_across_batches(self) -> None:
        _, disposition = self.add_disposition()
        self.write(name="other.json")
        result = intake_coverage(self.root)
        summary = result["summary"]
        self.assertEqual(summary["source_issue_count"], 2)
        self.assertEqual(summary["explicitly_unresolved_source_issue_count"], 2)
        self.assertEqual(summary["handled_disposition_count"], 1)
        untouched, handled = [batch["sources"][0]["source_issues"][0] for batch in result["batches"]]
        self.assertEqual(untouched["dispositions"], [])
        self.assertEqual(handled["issue"], fixture()["source_issues"][0])
        self.assertEqual(handled["dispositions"][0]["data"], disposition)
        self.assertEqual(handled["dispositions"][0]["evidence_verification"], "NOT_LOCALLY_VERIFIED")

    def test_status_missing_or_untyped_is_not_silently_counted_as_resolved(self) -> None:
        data = fixture()
        data["source_issues"][0]["issue_status"] = ["UNRESOLVED_SOURCE_WORDING"]
        self.write(data)
        result = intake_coverage(self.root)["summary"]
        self.assertEqual(result["source_issue_count"], 1)
        self.assertEqual(result["explicitly_unresolved_source_issue_count"], 0)
        self.assertEqual(result["source_issue_statuses"],
                         [{"value": ["UNRESOLVED_SOURCE_WORDING"], "count": 1}])
        self.assertNotIn("resolved_source_issue_count", result)

    def test_invalid_batch_fails_entire_cli_without_partial_output_or_mutation(self) -> None:
        self.write()
        self.write({"canonical": True}, "nested/broken.json")
        before = self.tree()
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = main(["--repo", str(self.root), "intake", "coverage"])
        self.assertEqual(result, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("invalid intake", stderr.getvalue())
        self.assertEqual(self.tree(), before)

    def test_stale_and_orphan_dispositions_fail_closed(self) -> None:
        path, data = self.add_disposition()
        for field, value in (("batch_sha256", "f" * 64), ("batch_path", "knowledge/intake/absent.json")):
            with self.subTest(field=field):
                changed = copy.deepcopy(data)
                changed["target"][field] = value
                path.write_text(json.dumps(changed), encoding="utf-8")
                with self.assertRaises(IntakeError):
                    intake_coverage(self.root)

    def test_cli_and_public_wrapper_are_read_only_in_fresh_external_workspace(self) -> None:
        initialize_workspace(self.root, schema_source_root=pcbknowledge_agent.REPO_ROOT)
        self.write()
        for entrypoint in (main, pcbknowledge_agent.main):
            before = self.tree()
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = entrypoint(["--repo", str(self.root), "intake", "coverage"])
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(stdout.getvalue()), intake_coverage(self.root))
            self.assertEqual(self.tree(), before)
        self.assertFalse((self.root / ".pcbknowledge").exists())

    def test_cli_does_not_initialize_layout_in_empty_git_repository(self) -> None:
        before = self.tree()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--repo", str(self.root), "intake", "coverage"]), 0)
        self.assertEqual(self.tree(), before)
        self.assertFalse((self.root / "knowledge/facts").exists())
        self.assertFalse((self.root / ".pcbknowledge").exists())

    def test_cli_rejects_unknown_and_abbreviated_filter_options(self) -> None:
        for option in ("--device", "--dev", "--published", "--unknown"):
            with self.subTest(option=option), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main(["--repo", str(self.root), "intake", "coverage", option, "SYNTH-A"])
                self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
