"""Workspace pinning, deterministic packaging and FreeCM receipt behavior."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from configs import pcbknowledge_workflow as workflow
from pcbknowledge.workspace import initialize_workspace, validate_workspace, validate_workspace_ref, WorkspaceError
from pcbknowledge.serialization import canonical_json
from pcbknowledge.v2.cli import main

ROOT=Path(__file__).resolve().parents[2]


class WorkspaceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'workspace'
        initialize_workspace(self.root,schema_source_root=ROOT,init_git=True)

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.root),*args])

    def test_initialization_is_idempotent_without_git_writes(self):
        self.assertTrue(initialize_workspace(self.root,schema_source_root=ROOT).replayed)
        self.assertEqual(self.git('diff','--cached','--name-only'),b'')
        self.assertEqual(validate_workspace(self.root).manifest.format,'pcbknowledge-workspace-v2')
        self.assertTrue((self.root/'knowledge/registry/parameters.json').is_file())

    def test_committed_ref_uses_its_own_pinned_schema_bytes(self):
        self.git('add','.')
        self.git('-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-qm','Synthetic fixture')
        committed=validate_workspace_ref(self.root)
        self.assertEqual(len(committed.commit),40)
        path=self.root/'schemas/part.schema.json';path.write_bytes(path.read_bytes()+b'\n')
        self.assertEqual(validate_workspace_ref(self.root).commit,committed.commit)
        with self.assertRaises(WorkspaceError):validate_workspace(self.root)

    def test_package_reads_only_selected_workspace_and_excludes_cache(self):
        cache=self.root/'.pcbknowledge/evidence/sha256/aa/original.pdf';cache.parent.mkdir(parents=True);cache.write_bytes(b'%PDF-synthetic')
        files=workflow.package_files(self.root)
        self.assertFalse(any('.pcbknowledge' in str(p) for p in files))
        self.assertFalse(any('parts/' in str(p) for p in files))
        self.assertIn(Path('knowledge/registry/parameters.json'),files)
        self.assertNotEqual(workflow.package_files(ROOT),files)

    def test_change_scope_prefers_staged_paths_and_rejects_mixed_commits(self):
        # Initialization files are untracked contract+data until deliberately split.
        self.git('add','pcbknowledge.workspace.json')
        with contextlib.redirect_stdout(io.StringIO()) as out:code=main(['--repo',str(self.root),'change-scope'])
        self.assertEqual(code,0);self.assertEqual(json.loads(out.getvalue())['scope'],'CODE_ONLY')
        self.git('add','knowledge/registry/parameters.json')
        with contextlib.redirect_stdout(io.StringIO()) as out:code=main(['--repo',str(self.root),'change-scope'])
        self.assertEqual(code,2);self.assertEqual(json.loads(out.getvalue())['scope'],'MIXED')

    def test_build_receipt_tracks_code_schema_and_static_assets(self):
        software=Path(self.temp.name)/'software';software.mkdir()
        paths=set(workflow.CONFIG_INPUTS)|set(workflow.BUILD_INPUT_FILES)
        for relative in paths:
            path=software/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((ROOT/relative).read_bytes())
        for relative in workflow.BUILD_INPUT_ROOTS:
            path=software/relative;path.mkdir(parents=True,exist_ok=True);(path/'owned.py').write_text('VALUE=1\n')
        workflow.write_configuration_receipt(software);workflow.write_build_receipt(software)
        workflow.require_build(software)
        path=software/'knowledge/registry/owned.py';path.write_text('VALUE=2\n')
        with self.assertRaises(workflow.WorkflowError):workflow.require_build(software)

    def test_explicit_missing_workspace_refuses_packaging(self):
        with self.assertRaises(WorkspaceError):workflow.package_files(self.root/'missing')

    def test_derived_state_ignore_rule_is_part_of_workspace_validation(self):
        (self.root/'.gitignore').write_text('# missing cache boundary\n')
        with self.assertRaisesRegex(WorkspaceError,'must ignore'):validate_workspace(self.root)

    def test_schema_and_knowledge_directory_symlinks_are_rejected(self):
        for name in ('schemas','knowledge'):
            with self.subTest(name=name):
                original=self.root/name;outside=Path(self.temp.name)/(name+'-outside')
                original.rename(outside);original.symlink_to(outside,target_is_directory=True)
                with self.assertRaisesRegex(WorkspaceError,'unsafe'):validate_workspace(self.root)
                original.unlink();outside.rename(original)
