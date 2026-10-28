"""Synthetic containment receipts; no component claims or original PDFs."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from configs import pcbknowledge_intake_eval as evaluation
from configs import pcbknowledge_workflow as workflow
from pcbknowledge.git_native.cli import main
from pcbknowledge.git_native.intake import IntakeError, MAX_INTAKE_BYTES, load_intake, search_intake, search_intake_issues
from pcbknowledge.git_native.intake_dispositions import DISPOSITION_FORMAT
from pcbknowledge.git_native.public_repo import public_distribution_violations
from pcbknowledge.git_native.workspace import initialize_workspace


def synthetic_batch() -> dict:
    return {"format": "pcbknowledge-independent-intake-v1", "canonical": False,
            "acceptance_status": "DRAFT", "sources": [
                {"id": "source-a", "device": "SYNTH-A", "package": "SYNTH-P",
                 "revision": "SYNTH-R", "pdf_sha256": "a" * 64, "status": "DRAFT",
                 "pdf_byte_size": 123, "pdf_pages": 2},
                {"id": "source-b", "device": "SYNTH-B", "status": "DRAFT"}],
            "facts": [{"id": "pin-a", "source_id": "source-a", "status": "DRAFT",
                       "parameter": "supply_pin", "value": 1},
                      {"id": "pin-b", "source_id": "source-b", "status": "DRAFT", "value": 2}],
            "source_issues": [{"id": "ambiguity-a", "source_id": "source-a",
                               "source_sha256": "a" * 64, "issue_status": "UNRESOLVED_SOURCE_WORDING",
                               "description": "Invented warning, not manufacturer evidence."}]}


def synthetic_disposition(batch_path: Path, relative: str) -> dict:
    return {"format": DISPOSITION_FORMAT, "id": "synthetic-containment", "canonical": False,
            "human_reviewed": False, "manufacturer_confirmed": False, "recorded_on": "2026-10-28",
            "acceptance_status": "AGENT_REVIEWED_UNDER_OWNER_DELEGATION",
            "disposition_status": "CONTAINED_BY_CONSERVATIVE_SUBSET",
            "source_issue_status": "UNRESOLVED_SOURCE_WORDING", "basis": "AGENT_CONSERVATIVE_INTERSECTION",
            "target": {"batch_path": relative, "batch_sha256": hashlib.sha256(batch_path.read_bytes()).hexdigest(),
                       "issue_id": "ambiguity-a", "source_id": "source-a", "source_sha256": "a" * 64,
                       "device": "SYNTH-A", "package": "SYNTH-P", "revision": "SYNTH-R"},
            "policy": {"screening_only": True, "parameter": "supply_voltage_vs_ambient_temperature",
                       "supply_v": {"min": 2, "max": 4, "inclusive": True},
                       "ambient_c": {"min": -10, "max": 50, "inclusive": True},
                       "inside_result": "WITHIN_CONSERVATIVE_SUPPLY_AMBIENT_SUBSET",
                       "outside_result": "NOT_ESTABLISHED", "automatic_recommendation": False,
                       "limitations": ["Invented numeric fixture; not a whole-circuit approval."]},
            "summary": "Synthetic only.", "remaining_evidence_needed": "Invented clarification.",
            "history_policy": "One receipt per target; successor lifecycle requires explicit extension.",
            "evidence": [{"role": role, "url": "https://example.invalid/synthetic", "sha256": digest,
                          "byte_size": 123, "accessed_on": "2026-10-28", "retrieved_at": "2026-10-28T00:00:00Z",
                          "revision": revision, "revision_date": "2026-10", "pdf_pages": 2,
                          "locators": [{"printed_page": 1, "pdf_page_index": 0, "section": "Invented",
                                        "visual_checked": True}], "method": "Synthetic fixture, no real source.",
                          "finding": "Synthetic only.", "redistribution_license": "Not asserted; original excluded",
                          "latest_revision_guaranteed": False}
                         for role, digest, revision in (("HISTORICAL_SOURCE", "a" * 64, "SYNTH-R"),
                                                        ("RECHECK_DATASHEET", "b" * 64, "SYNTH-R2"))],
            "review": {"actor_type": "AGENT", "authority": "OWNER_DELEGATION", "actor_id": "agent:synthetic-a",
                       "independent_reviewer": "agent:synthetic-b", "reviewed_at": "2026-10-28T00:00:00Z",
                       "independent_review_basis": "Synthetic provenance."}}


class IntakeDispositionTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        self.relative = "knowledge/intake/synthetic.json"
        self.batch_path = self.root / self.relative
        self.batch_path.parent.mkdir(parents=True)
        self.batch = synthetic_batch()
        self.batch_path.write_text(json.dumps(self.batch), encoding="utf-8")
        self.path = self.root / "knowledge/intake-dispositions/synthetic.json"
        self.path.parent.mkdir()
        self.data = synthetic_disposition(self.batch_path, self.relative)
        self.write()

    def write(self, data: dict | None = None) -> None:
        self.path.write_text(json.dumps(self.data if data is None else data), encoding="utf-8")

    def manifests(self) -> tuple[dict, dict]:
        case = {"id": "original-fact", "command": "search", "query": "", "filters": {"device": "SYNTH-A"},
                "expected": [self.relative + "#pin-a"]}
        base = {"format": evaluation.FORMAT, "files": {
            self.relative: hashlib.sha256(self.batch_path.read_bytes()).hexdigest()}, "cases": [case]}
        supplement = {"format": evaluation.DISPOSITION_EVAL_FORMAT, "files": {
            self.path.relative_to(self.root).as_posix(): hashlib.sha256(self.path.read_bytes()).hexdigest()},
            "cases": [{"id": "policy-warning", "command": "issues", "query": "CONTAINED_BY_CONSERVATIVE_SUBSET",
                       "filters": {}, "expected": [self.relative + "#ambiguity-a"]}]}
        return base, supplement

    def test_originals_unchanged_policy_inline_and_not_promoted_to_fact(self) -> None:
        before = self.batch_path.read_bytes()
        fact = search_intake(self.root, device="SYNTH-A")[0]
        issue = search_intake_issues(self.root, "CONTAINED_BY_CONSERVATIVE_SUBSET")[0]
        self.assertEqual(fact["fact"], self.batch["facts"][0])
        self.assertEqual(fact["source_issues"], self.batch["source_issues"])
        self.assertEqual(issue["source_issue"], self.batch["source_issues"][0])
        self.assertEqual(fact["source_issue_dispositions"], issue["source_issue_dispositions"])
        receipt = issue["source_issue_dispositions"][0]
        self.assertEqual(receipt["data"], self.data)
        self.assertEqual(receipt["evidence_verification"], "NOT_LOCALLY_VERIFIED")
        self.assertFalse(receipt["canonical"])
        self.assertFalse((self.root / ".pcbknowledge/evidence").exists())
        self.assertEqual(search_intake(self.root, "CONTAINED_BY_CONSERVATIVE_SUBSET"), [])
        self.assertNotIn("source_issue_dispositions", search_intake(self.root, device="SYNTH-B")[0])
        self.assertEqual(before, self.batch_path.read_bytes())

    def test_source_id_reuse_in_other_batch_does_not_leak_policy(self) -> None:
        other = self.batch_path.with_name("other.json")
        other.write_bytes(self.batch_path.read_bytes())
        matches = search_intake_issues(self.root)
        self.assertNotIn("source_issue_dispositions", matches[0])
        self.assertIn("source_issue_dispositions", matches[1])

    def test_all_exact_target_pins_fail_closed_even_nonmatching_queries(self) -> None:
        for key in self.data["target"]:
            with self.subTest(key=key):
                mutated = copy.deepcopy(self.data)
                mutated["target"][key] = "c" * 64 if key.endswith("sha256") else "wrong"
                self.write(mutated)
                for read in (load_intake, lambda r: search_intake(r, device="ABSENT"),
                             lambda r: search_intake_issues(r, "never"), workflow.package_files):
                    with self.assertRaises(IntakeError):
                        read(self.root)
        self.write()
        self.batch_path.write_bytes(self.batch_path.read_bytes() + b"\n")
        with self.assertRaisesRegex(IntakeError, "stale"):
            load_intake(self.root)

    def test_forged_resolution_authority_and_unbounded_policy_fail(self) -> None:
        mutations = [({"canonical": True}, None), ({"manufacturer_confirmed": True}, None),
                     ({"human_reviewed": True}, None), ({"disposition_status": "RESOLVED"}, None),
                     ({"source_issue_status": "RESOLVED"}, None), ({"basis": "VENDOR_CONFIRMED"}, None),
                     ({"actor_type": "HUMAN"}, "review"), ({"reviewed_at": "not-a-date"}, "review"),
                     ({"reviewed_at": "2026-10-28T00:00:00"}, "review"), ({"authority": "HUMAN"}, "review"),
                     ({"independent_reviewer": "agent:synthetic-a"}, "review"),
                     ({"automatic_recommendation": True}, "policy"), ({"screening_only": False}, "policy"),
                     ({"outside_result": "UNSAFE"}, "policy"), ({"inside_result": "DESIGN_APPROVED"}, "policy"),
                     ({"limitations": []}, "policy")]
        for mutation, key in mutations:
            with self.subTest(mutation=mutation):
                data = copy.deepcopy(self.data)
                (data[key] if key else data).update(mutation)
                self.write(data)
                with self.assertRaises(IntakeError):
                    load_intake(self.root)

    def test_missing_or_malformed_evidence_association_and_geometry_fail(self) -> None:
        mutations = [lambda d: d.update(evidence=[]),
                     lambda d: d["evidence"].pop(0),
                     lambda d: d["evidence"][0].update(sha256="c" * 64),
                     lambda d: d["evidence"][0].update(revision="wrong"),
                     lambda d: d["evidence"][0].update(byte_size=124),
                     lambda d: d["evidence"][0].update(pdf_pages=3),
                     lambda d: d["evidence"][1].update(role="HISTORICAL_SOURCE"),
                     lambda d: d["evidence"][1].update(locators=[]),
                     lambda d: d["evidence"][1].update(pdf_pages=True),
                     lambda d: d["evidence"][1].update(latest_revision_guaranteed=True),
                     lambda d: d["evidence"][1]["locators"][0].update(pdf_page_index=2),
                     lambda d: d["evidence"][1]["locators"][0].update(visual_checked=False),
                     lambda d: d["evidence"][1]["locators"].append(d["evidence"][1]["locators"][0]),
                     lambda d: d.update(undocumented_resolution=True)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                data = copy.deepcopy(self.data)
                mutate(data)
                self.write(data)
                with self.assertRaises(IntakeError):
                    load_intake(self.root)

    def test_numeric_bounds_are_finite_ordered_and_not_booleans(self) -> None:
        for value in (True, float("nan"), float("inf"), "2", None, 5, 10 ** 1000):
            with self.subTest(value=value):
                data = copy.deepcopy(self.data)
                data["policy"]["supply_v"]["min"] = value
                self.write(data)
                with self.assertRaises(IntakeError):
                    load_intake(self.root)
        data = copy.deepcopy(self.data)
        data["policy"]["supply_v"]["inclusive"] = False
        self.write(data)
        with self.assertRaises(IntakeError):
            load_intake(self.root)

    def test_ambiguous_duplicate_receipt_and_duplicate_keys_fail(self) -> None:
        duplicate = self.path.with_name("duplicate.json")
        duplicate.write_bytes(self.path.read_bytes())
        with self.assertRaisesRegex(IntakeError, "duplicate disposition"):
            load_intake(self.root)
        duplicate.unlink()
        self.path.write_text('{"format":"first","format":"second"}', encoding="utf-8")
        with self.assertRaisesRegex(IntakeError, "duplicate JSON key"):
            load_intake(self.root)

    def test_orphan_without_intake_directory_fails(self) -> None:
        self.batch_path.unlink()
        self.batch_path.parent.rmdir()
        with self.assertRaisesRegex(IntakeError, "orphan"):
            load_intake(self.root)

    def test_oversize_malformed_and_symlink_fail(self) -> None:
        self.path.write_bytes(b" " * (MAX_INTAKE_BYTES + 1))
        with self.assertRaises(IntakeError):
            load_intake(self.root)
        self.path.write_text('not JSON', encoding="utf-8")
        with self.assertRaises(IntakeError):
            load_intake(self.root)
        self.write()
        # Mock only symlink detection, so this safety regression runs on Windows
        # without requiring the privilege to create a native symlink.
        original = Path.is_symlink
        with mock.patch.object(Path, "is_symlink", lambda path: path == self.path or original(path)):
            with self.assertRaisesRegex(IntakeError, "symlink"):
                load_intake(self.root)

    def test_cli_list_issues_validate_and_package_share_validation(self) -> None:
        for command in (("intake", "list"), ("intake", "issues", "NOT_ESTABLISHED"), ("validate",)):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["--repo", str(self.root), *command]), 0)
            self.assertTrue(json.loads(output.getvalue()))
        paths = workflow.package_files(self.root)
        self.assertIn(self.path.relative_to(self.root), paths)
        self.assertIn(self.batch_path.relative_to(self.root), paths)
        self.assertTrue(all(path.suffix in (".json", ".schema") for path in paths))
        self.assertEqual(public_distribution_violations([self.path.relative_to(self.root).as_posix()]), ())
        self.assertTrue(public_distribution_violations(["knowledge/intake-dispositions/original.pdf"]))

    def test_supplement_eval_requires_separate_exact_pins_and_metadata(self) -> None:
        base, supplement = self.manifests()
        with self.assertRaisesRegex(evaluation.EvaluationError, "separately pinned"):
            evaluation.evaluate(self.root, base)
        report = evaluation.evaluate(self.root, base, disposition_manifest=supplement)
        self.assertEqual((report["status"], report["case_count"], report["disposition_count"]), ("PASS", 2, 1))
        def runner(root, case):
            result = evaluation.run_cli(root, case)
            del result[0]["source_issue_dispositions"]
            return result
        self.assertEqual(evaluation.evaluate(self.root, base, disposition_manifest=supplement,
                                             runner=runner)["status"], "FAIL")
        self.path.write_bytes(self.path.read_bytes() + b"\n")
        with self.assertRaisesRegex(evaluation.EvaluationError, "disposition bytes"):
            evaluation.evaluate(self.root, base, disposition_manifest=supplement)

    def test_changed_disposition_during_replay_is_not_a_pass(self) -> None:
        base, supplement = self.manifests()
        def runner(root, case):
            result = evaluation.run_cli(root, case)
            self.path.write_bytes(self.path.read_bytes() + b"\n")
            return result
        with self.assertRaisesRegex(evaluation.EvaluationError, "dispositions changed"):
            evaluation.evaluate(self.root, base, disposition_manifest=supplement, runner=runner)

    def test_plain_intake_without_disposition_retains_existing_projection(self) -> None:
        self.path.unlink()
        self.assertNotIn("source_issue_dispositions", search_intake(self.root)[0])
        base = {"format": evaluation.FORMAT,
                "files": {self.relative: hashlib.sha256(self.batch_path.read_bytes()).hexdigest()},
                "cases": [{"id": "plain", "command": "issues", "query": "", "filters": {},
                           "expected": [self.relative + "#ambiguity-a"]}]}
        self.assertEqual(evaluation.evaluate(self.root, base)["status"], "PASS")
