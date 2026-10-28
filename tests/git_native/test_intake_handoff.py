"""Synthetic real-object handoff tests, without source originals or network."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from configs import pcbknowledge_intake_handoff as handoff


class IntakeHandoffTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.repo = self.root / "repo"
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.git("config", "user.name", "Synthetic")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.git("commit", "--allow-empty", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.path = "knowledge/intake/synthetic.json"
        self.review = "knowledge/intake/synthetic-review.md"
        self.data = {
            "format": "pcbknowledge-independent-intake-v1", "canonical": False,
            "human_reviewed": False, "acceptance_status": "DRAFT",
            "sources": [{"id": "source", "status": "DRAFT", "device": "SYNTHETIC"}],
            "facts": [{"id": "fact", "status": "DRAFT", "source_id": "source"}],
            "source_issues": [{"id": "warning", "source_id": "source"}],
        }
        self.payloads = {self.path: json.dumps(self.data).encode(), self.review: b"Synthetic review.\n"}
        self.delivery = self.commit(self.payloads)
        self.target = self.base
        self.pins = {p: hashlib.sha256(b).hexdigest() for p, b in self.payloads.items()}

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True)

    def commit(self, files, base=None, modes=None, extra_parent=None):
        entries = []
        for path, payload in files.items():
            oid = subprocess.check_output(["git", "-C", str(self.repo), "hash-object", "-w", "--stdin"],
                                          input=payload).decode().strip()
            entries.append((path, (modes or {}).get(path, "100644"), oid))
        # A temporary index constructs arbitrary additive synthetic trees.
        env = {**os.environ, "GIT_INDEX_FILE": str(self.root / "index")}
        def run(*args, payload=None):
            return subprocess.check_output(["git", "-C", str(self.repo), *args], env=env, input=payload).decode().strip()
        run("read-tree", base or self.base)
        for path, mode, oid in entries:
            run("update-index", "--add", "--cacheinfo", mode, oid, path)
        tree = run("write-tree")
        parents = ["-p", base or self.base]
        if extra_parent:
            parents += ["-p", extra_parent]
        return run("commit-tree", tree, *parents, payload=b"Synthetic delivery\n")

    def inspect(self):
        return handoff.inspect(self.repo, self.delivery, self.base, self.target,
                               self.pins[self.path], self.pins[self.review])

    def reject(self):
        with self.assertRaises((ValueError, UnicodeError)):
            self.inspect()

    def replace_json(self, payload):
        self.payloads[self.path] = payload
        self.pins[self.path] = hashlib.sha256(payload).hexdigest()
        self.delivery = self.commit(self.payloads)

    def test_valid_dirty_worktree_and_no_approval(self):
        (self.repo / "untracked").write_text("untouched")
        before = self.git("status", "--porcelain")
        result = self.inspect()
        self.assertEqual(result["status"], "PREFLIGHT_COMPATIBLE_ONLY")
        self.assertFalse(result["approval"])
        self.assertEqual(result["aggregate"], "NOT_RUN")
        self.assertEqual(result["target_commit"], self.target)
        self.assertEqual(self.git("status", "--porcelain"), before)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), self.base)
        self.assertEqual(result["files"][self.path]["bytes"], len(self.payloads[self.path]))

    def test_same_ids_device_and_source_in_other_batch_are_legal(self):
        self.target = self.commit({"knowledge/intake/another.json": self.payloads[self.path]})
        self.assertEqual(self.inspect()["status"], "PREFLIGHT_COMPATIBLE_ONLY")

    def test_pin_mismatch(self):
        self.pins[self.path] = "0" * 64
        self.reject()

    def test_invalid_pins_and_commit_identifiers(self):
        for value in ("HEAD", "--help", "a" * 39, "A" * 40):
            with self.subTest(value=value):
                self.delivery = value
                self.reject()

    def test_missing_object(self):
        self.delivery = "0" * 40
        self.reject()

    def test_not_commit(self):
        self.delivery = self.git("rev-parse", self.delivery + "^{tree}").strip()
        self.reject()

    def test_wrong_parent(self):
        self.base = self.delivery
        self.reject()

    def test_merge(self):
        other = self.commit({"other": b"synthetic"})
        self.delivery = self.commit(self.payloads, extra_parent=other)
        self.reject()

    def test_add_only_and_target_path_collision(self):
        self.target = self.delivery
        self.reject()
        self.target = self.base
        self.base = self.delivery
        self.delivery = self.commit({self.path: b"changed"}, base=self.base)
        self.reject()

    def test_extra_file_and_unmatched_pair(self):
        for files in ({**self.payloads, "extra": b"x"}, {self.path: self.payloads[self.path],
                      "knowledge/intake/wrong-review.md": b"x"}):
            self.delivery = self.commit(files)
            self.reject()

    def test_nonregular_and_executable_pair(self):
        for mode in ("120000", "100755"):
            self.delivery = self.commit(self.payloads, modes={self.review: mode})
            self.reject()

    def test_unsafe_target_ancestor_and_directory_collision(self):
        for path in ("knowledge", "knowledge/intake", self.path + "/child"):
            self.target = self.commit({path: b"x"})
            self.reject()

    def test_duplicate_json_and_nonfinite_and_utf8(self):
        for payload in (b'{"canonical": false,' + self.payloads[self.path][1:],
                        self.payloads[self.path].replace(b'false', b'NaN', 1), b"\xff"):
            self.replace_json(payload)
            self.reject()

    def test_batch_local_id_and_warning_reference_validation(self):
        for kind in ("sources", "facts", "source_issues"):
            data = copy.deepcopy(self.data)
            data[kind].append(data[kind][0])
            self.replace_json(json.dumps(data).encode())
            self.reject()
        data = copy.deepcopy(self.data)
        data["source_issues"][0]["source_id"] = "missing"
        self.replace_json(json.dumps(data).encode())
        self.reject()

    def test_human_marker_required(self):
        data = copy.deepcopy(self.data)
        del data["human_reviewed"]
        self.replace_json(json.dumps(data).encode())
        self.reject()

    def test_oversize_checked_before_blob_read(self):
        self.replace_json(b" " * (handoff.MAX_INTAKE_BYTES + 1))
        original = handoff.Objects.run
        def guarded(instance, *args):
            self.assertNotEqual(args[:2], ("cat-file", "blob"))
            return original(instance, *args)
        with patch.object(handoff.Objects, "run", guarded):
            self.reject()

    def test_hostile_environment_and_repository_config_are_not_loaded(self):
        marker = self.root / "executed"
        config = self.root / "hostile-config"
        config.write_text("[include]\n path = /definitely/not/read\n[core]\n fsmonitor = touch " + str(marker))
        self.git("config", "core.fsmonitor", "touch " + str(marker))
        self.git("config", "remote.origin.url", "ext::touch " + str(marker))
        with patch.dict(os.environ, {"GIT_CONFIG": str(config), "GIT_DIR": "/absent",
                "GIT_WORK_TREE": "/absent", "GIT_OBJECT_DIRECTORY": "/absent",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES": "/absent", "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.fsmonitor", "GIT_CONFIG_VALUE_0": "touch " + str(marker)}):
            self.assertEqual(self.inspect()["status"], "PREFLIGHT_COMPATIBLE_ONLY")
        self.assertFalse(marker.exists())

    def test_alternates_rejected(self):
        path = self.repo / ".git/objects/info/alternates"
        path.write_text("/absent\n")
        self.reject()

    def test_forged_git_object_identity_rejected(self):
        objects = self.repo / ".git/objects"
        original = objects / self.delivery[:2] / self.delivery[2:]
        forged = "1" * 40
        destination = objects / forged[:2] / forged[2:]
        destination.parent.mkdir(exist_ok=True)
        shutil.copyfile(original, destination)
        self.delivery = forged
        self.reject()

    def test_object_symlinks_or_reparse_points_rejected(self):
        path = self.repo / ".git/objects/info"
        original = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda item: item == path or original(item)):
            self.reject()

    def test_windows_reparse_attribute_rejected(self):
        original = Path.lstat
        target = self.repo / ".git/objects/info"
        def lstat(path, *args, **kwargs):
            if path == target:
                return SimpleNamespace(st_file_attributes=1024, st_mode=original(path).st_mode)
            return original(path, *args, **kwargs)
        with patch.object(handoff.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024, create=True), \
                patch.object(Path, "lstat", lstat):
            self.reject()

    def test_temp_directory_inside_input_rejected_without_writes(self):
        before = set(self.repo.iterdir())
        with patch.object(tempfile, "tempdir", str(self.repo)):
            self.reject()
        self.assertEqual(set(self.repo.iterdir()), before)

    def test_bare_repository(self):
        self.repo = self.repo / ".git"
        self.assertEqual(self.inspect()["status"], "PREFLIGHT_COMPATIBLE_ONLY")

    def test_cli_rejection(self):
        args = ["--object-repo", str(self.repo), "--delivery", "HEAD", "--base", self.base,
                "--target", self.target, "--json-sha256", self.pins[self.path],
                "--review-sha256", self.pins[self.review]]
        result = subprocess.run([os.sys.executable, str(Path(handoff.__file__)), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "PREFLIGHT_REJECTED")


if __name__ == "__main__":
    unittest.main()
