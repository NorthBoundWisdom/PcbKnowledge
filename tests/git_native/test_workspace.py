from __future__ import annotations

import contextlib
import http.client
import io
import json
import subprocess
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

from configs import pcbknowledge_workflow as workflow
from configs.pcbknowledge_agent import main as agent_main
from pcbknowledge.git_native.model import LicenseClass, PreparedBy
from pcbknowledge.git_native.public_repo import check_public_distribution
from pcbknowledge.git_native.store import KnowledgeRepository
from pcbknowledge.git_native.workspace import (
    SCHEMA_PATHS,
    WORKSPACE_MANIFEST_PATH,
    WorkspaceError,
    initialize_workspace,
    schema_digest,
    validate_workspace,
    validate_workspace_ref,
)
from pcbknowledge.git_native.workspace_server import create_server
from tests.git_native.support import minimal_pdf
from tests.git_native.test_workflow import WorkflowTestCase


class WorkspaceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.parent = Path(self.temporary.name)
        self.source_root = Path(__file__).resolve().parents[2]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git_workspace(self, name: str = "knowledge") -> Path:
        root = self.parent / name
        root.mkdir()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        return root

    def initialize(self, root: Path):
        return initialize_workspace(root, schema_source_root=self.source_root)

    @staticmethod
    def commit_all(root: Path, message: str = "workspace contract") -> None:
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-q",
                "-m",
                message,
            ],
            cwd=root,
            check=True,
        )

    def test_initialize_workspace_is_deterministic_unstaged_and_idempotent(self) -> None:
        root = self.git_workspace()
        first = self.initialize(root)

        self.assertFalse(first.replayed)
        self.assertEqual(first.validation.manifest.schema_digest, schema_digest(self.source_root))
        self.assertEqual(
            json.loads((root / WORKSPACE_MANIFEST_PATH).read_text("utf-8"))["format"],
            "pcbknowledge-workspace-v1",
        )
        for relative in SCHEMA_PATHS:
            self.assertEqual(
                (root / relative).read_bytes(),
                (self.source_root / relative).read_bytes(),
            )
        for relative in (
            "knowledge/sources/.gitkeep",
            "knowledge/entities/.gitkeep",
            "knowledge/facts/.gitkeep",
            "evidence/sha256/.gitkeep",
        ):
            self.assertTrue((root / relative).is_file())
        cached = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=root, check=False
        )
        self.assertEqual(cached.returncode, 0, "workspace init must not stage files")

        second = self.initialize(root)
        self.assertTrue(second.replayed)
        self.assertEqual(second.validation.manifest, first.validation.manifest)

    def test_initialize_rejects_non_git_and_conflicting_authority(self) -> None:
        not_git = self.parent / "not-git"
        not_git.mkdir()
        with self.assertRaisesRegex(WorkspaceError, "not a Git repository"):
            self.initialize(not_git)

        conflict = self.git_workspace("conflict")
        path = conflict / "knowledge/sources/real.json"
        path.parent.mkdir(parents=True)
        path.write_text("{}\n", encoding="utf-8")
        self.commit_all(conflict, "conflicting authority")
        with self.assertRaisesRegex(WorkspaceError, "not empty"):
            self.initialize(conflict)

    def test_init_git_only_accepts_missing_or_empty_target(self) -> None:
        generated = self.parent / "generated"
        result = initialize_workspace(
            generated, schema_source_root=self.source_root, init_git=True
        )
        self.assertFalse(result.replayed)
        self.assertEqual(validate_workspace(generated).root, generated.resolve())

        occupied = self.parent / "occupied"
        occupied.mkdir()
        (occupied / "note.txt").write_text("user-owned\n", encoding="utf-8")
        with self.assertRaisesRegex(WorkspaceError, "missing or empty"):
            initialize_workspace(
                occupied, schema_source_root=self.source_root, init_git=True
            )

    def test_workspace_ref_pins_manifest_and_exact_schema_snapshot(self) -> None:
        root = self.git_workspace()
        self.initialize(root)
        self.commit_all(root)

        published = validate_workspace_ref(root)
        self.assertEqual(published.manifest.schema_digest, schema_digest(root))
        self.assertIsNotNone(published.commit)

        source_schema = root / SCHEMA_PATHS[0]
        original = source_schema.read_text("utf-8")
        source_schema.write_text(original + "\n", encoding="utf-8")
        with self.assertRaisesRegex(WorkspaceError, "schema digest"):
            validate_workspace(root)
        self.assertEqual(validate_workspace_ref(root).commit, published.commit)

        subprocess.run(
            ["git", "add", source_schema.relative_to(root)], cwd=root, check=True
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-q",
                "-m",
                "tamper schema without manifest",
            ],
            cwd=root,
            check=True,
        )
        with self.assertRaisesRegex(WorkspaceError, "schema digest"):
            validate_workspace_ref(root)

    def test_agent_wrapper_targets_only_the_selected_external_workspace(self) -> None:
        root = self.git_workspace()
        self.initialize(root)
        self.commit_all(root)
        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = agent_main(
                [
                    "--repo",
                    str(root),
                    "source",
                    "create",
                    "--idempotency-key",
                    "external-agent-source",
                    "--title",
                    "External workspace source",
                ]
            )
        self.assertEqual((code, errors.getvalue()), (0, ""))
        source = json.loads(output.getvalue())
        self.assertTrue((root / f"knowledge/sources/{source['id']}.json").is_file())
        self.assertEqual(check_public_distribution(self.source_root), ())

    def test_workspace_gui_identifies_external_root(self) -> None:
        root = self.git_workspace()
        self.initialize(root)
        self.commit_all(root)
        server = create_server(root, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_port, timeout=3
            )
            connection.request("GET", "/")
            response = connection.getresponse()
            payload = response.read().decode("utf-8")
            connection.close()
            self.assertEqual(response.status, 200)
            self.assertIn("Selected knowledge workspace", payload)
            self.assertIn(str(root.resolve()), payload)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class WorkspacePackagingTests(WorkflowTestCase):
    def _external_workspace(self) -> Path:
        external = Path(self.temporary.name) / "external-workspace"
        external.mkdir()
        subprocess.run(["git", "init", "-q", str(external)], check=True)
        initialize_workspace(external, schema_source_root=self.root)
        subprocess.run(["git", "add", "-A"], cwd=external, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-q",
                "-m",
                "workspace contract",
            ],
            cwd=external,
            check=True,
        )
        return external

    def test_package_reads_external_workspace_and_writes_output_to_software_root(self) -> None:
        external = self._external_workspace()
        repository = KnowledgeRepository(external)
        repository.ensure_layout()
        source = repository.create_source(
            prepared_by=PreparedBy.AGENT,
            idempotency_key="external-package-source",
        )
        evidence = repository.import_pdf_bytes(minimal_pdf("external workspace"))
        updated = source.edit(
            title="External package fixture",
            document_number="PK-EXT-1",
            revision="A",
            source_locator="https://example.invalid/external.pdf",
            source_publisher="PcbKnowledge Fixtures",
            license_class=LicenseClass.OPEN_LICENSE,
            license_note="Synthetic fixture",
            evidence=evidence,
            preparation_note=None,
            supersedes=None,
        )
        repository.save_source(source, updated, source.revision_token)
        self.prepare_receipts()

        output = workflow.create_package(external, software_root=self.root)
        self.assertEqual(output.parent, self.root / workflow.PACKAGE_DIRECTORY)
        self.assertFalse((external / "build").exists())
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            self.assertIn(WORKSPACE_MANIFEST_PATH.as_posix(), names)
            self.assertIn(f"knowledge/sources/{source.id}.json", names)
            self.assertIn(evidence.path, names)
            self.assertEqual(
                json.loads(archive.read("MANIFEST.json"))["format"],
                workflow.PACKAGE_FORMAT,
            )

    def test_workflow_parser_accepts_workspace_only_for_data_runtime_actions(self) -> None:
        external = str(Path(self.temporary.name) / "external")
        for action in ("run", "open", "test", "package"):
            arguments = workflow.parse_args([action, "--workspace", external])
            self.assertEqual(arguments.workspace, external)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                workflow.parse_args(["build", "--workspace", external])


if __name__ == "__main__":
    unittest.main()
