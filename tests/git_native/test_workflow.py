from __future__ import annotations

import json
import contextlib
import io
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from configs import pcbknowledge_workflow as workflow
from pcbknowledge.git_native.model import PreparedBy
from pcbknowledge.git_native.store import KnowledgeRepository
from tests.git_native.support import minimal_pdf


class WorkflowTestCase(unittest.TestCase):
    temporary: tempfile.TemporaryDirectory[str]
    root: Path

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        for relative in workflow.CONFIG_INPUTS:
            source = workflow.REPO_ROOT / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
        for relative in workflow.BUILD_INPUT_FILES:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                destination.write_text(f"build input {relative}\n", encoding="utf-8")
        for relative in workflow.BUILD_INPUT_ROOTS:
            directory = self.root / relative
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "owned.py").write_text("VALUE = 1\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def prepare_receipts(self) -> None:
        workflow.write_configuration_receipt(self.root)
        workflow.write_build_receipt(self.root)


class LocalWorkflowTests(WorkflowTestCase):
    def test_configuration_receipt_is_exactly_bound_to_declared_inputs(self) -> None:
        path = workflow.write_configuration_receipt(self.root)
        receipt = workflow.require_configuration(self.root)

        self.assertEqual(path, self.root / workflow.CONFIG_RECEIPT)
        self.assertEqual(receipt["configurationId"], workflow.CONFIGURATION_ID)
        manifest = self.root / "configs/freecm.commands.jsonc"
        manifest.write_text(manifest.read_text("utf-8") + "\n", encoding="utf-8")
        with self.assertRaisesRegex(workflow.WorkflowError, "Config inputs changed"):
            workflow.require_configuration(self.root)

    def test_build_receipt_rejects_source_drift_but_not_knowledge_edits(self) -> None:
        self.prepare_receipts()
        workflow.require_build(self.root)

        knowledge = self.root / "knowledge/records/local-note.txt"
        knowledge.parent.mkdir(parents=True)
        knowledge.write_text("a data edit does not rebuild the editor\n", encoding="utf-8")
        workflow.require_build(self.root)

        source = self.root / workflow.BUILD_INPUT_ROOTS[0] / "owned.py"
        source.write_text("VALUE = 2\n", encoding="utf-8")
        with self.assertRaisesRegex(workflow.WorkflowError, "source changed"):
            workflow.require_build(self.root)

    def test_source_dependency_template_must_remain_empty(self) -> None:
        workflow._require_prerequisites(self.root)
        template = self.root / "source_roots.lock.jsonc.in"
        value = json.loads(template.read_text("utf-8"))
        value["dependencies"] = {"unexpected": {"url": "file:///tmp/dependency"}}
        template.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(workflow.WorkflowError, "dependencies empty"):
            workflow._require_prerequisites(self.root)

    def test_build_signature_ignores_python_cache_only(self) -> None:
        before = workflow.build_signature(self.root)
        cache = self.root / workflow.BUILD_INPUT_ROOTS[0] / "__pycache__/ignored.pyc"
        cache.parent.mkdir()
        cache.write_bytes(b"cache")
        self.assertEqual(workflow.build_signature(self.root), before)

        extra = self.root / workflow.BUILD_INPUT_ROOTS[0] / "new_module.py"
        extra.write_text("NEW = True\n", encoding="utf-8")
        self.assertNotEqual(workflow.build_signature(self.root), before)

    def test_package_is_reproducible_and_contains_only_validated_data(self) -> None:
        repository = KnowledgeRepository(self.root)
        repository.ensure_layout()
        record = repository.create(prepared_by=PreparedBy.AGENT, idempotency_key="package")
        evidence = repository.import_pdf_bytes(minimal_pdf("package"))
        updated = record.edit(
            title="Package fixture",
            document_number=None,
            revision="A",
            source_locator=None,
            source_publisher="Fixture",
            license_class=record.license_class,
            license_note=None,
            evidence=evidence,
            preparation_note=None,
            supersedes=None,
        )
        repository.save(record, updated, record.revision_token)
        self.prepare_receipts()

        first = workflow.create_package(self.root)
        first_bytes = first.read_bytes()
        second = workflow.create_package(self.root)

        self.assertEqual(second, first)
        self.assertEqual(second.read_bytes(), first_bytes)
        with zipfile.ZipFile(first) as archive:
            names = archive.namelist()
            self.assertIn("MANIFEST.json", names)
            self.assertIn(f"knowledge/records/{record.id}.json", names)
            self.assertIn(evidence.path, names)
            self.assertIn("schemas/knowledge-record.schema.json", names)
            manifest = json.loads(archive.read("MANIFEST.json"))
            self.assertEqual(manifest["format"], workflow.PACKAGE_FORMAT)
        sidecar = first.with_suffix(first.suffix + ".sha256")
        self.assertTrue(sidecar.read_text("ascii").endswith(f"  {first.name}\n"))

    def test_manifest_and_workflow_are_native_and_receipt_bound(self) -> None:
        manifest = json.loads(
            (workflow.REPO_ROOT / "configs/freecm.commands.jsonc").read_text("utf-8")
        )
        configuration = manifest["commands"]["config"][0]

        self.assertEqual(configuration["id"], workflow.CONFIGURATION_ID)
        self.assertEqual(
            configuration["readiness"]["inputs"],
            [path.as_posix() for path in workflow.CONFIG_INPUTS],
        )
        self.assertEqual(
            configuration["readiness"]["outputs"],
            [workflow.CONFIG_RECEIPT.as_posix()],
        )
        self.assertEqual(configuration["defaults"]["run"], "local-editor")
        self.assertNotIn("docker", json.dumps(manifest).lower())
        self.assertNotIn("docker", (workflow.REPO_ROOT / "configs/pcbknowledge_workflow.py").read_text("utf-8").lower())

    def test_double_click_launcher_is_safe_and_build_receipt_bound(self) -> None:
        launcher = workflow.REPO_ROOT / "Open PcbKnowledge.command"
        source = launcher.read_text("utf-8")

        self.assertIn(Path("Open PcbKnowledge.command"), workflow.BUILD_INPUT_FILES)
        self.assertTrue(os.access(launcher, os.X_OK))
        self.assertIn("pcbknowledge_workflow.py open", source)
        self.assertNotIn("docker", source.lower())
        self.assertNotIn("git commit", source.lower())
        self.assertNotIn("password", source.lower())

    def test_run_only_arguments_are_rejected_for_other_actions(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                workflow.parse_args(["build", "--no-browser"])
            with self.assertRaises(SystemExit):
                workflow.parse_args(["test", "--port", "18081"])
        arguments = workflow.parse_args(["run", "--port", "18081", "--no-browser"])
        self.assertEqual((arguments.port, arguments.no_browser), (18081, True))
        open_arguments = workflow.parse_args(["open", "--port", "18082", "--no-browser"])
        self.assertEqual((open_arguments.port, open_arguments.no_browser), (18082, True))


if __name__ == "__main__":
    unittest.main()
