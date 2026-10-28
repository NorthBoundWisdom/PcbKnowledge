#!/usr/bin/env python3
"""Offline additive intake-pair compatibility; never approval or integration."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pcbknowledge.git_native.intake import (  # noqa: E402
    IntakeError, MAX_INTAKE_BYTES, _reject_constant, _source_issues,
    _unique_object, _validate_batch,
)


class HandoffError(ValueError):
    """The pinned local handoff cannot establish compatibility."""


def require(condition, message):
    if not condition:
        raise HandoffError(message)


class Objects:
    """Read SHA-1 objects without trusting repository config, refs or worktree."""

    def __init__(self, repo, control):
        root = Path(repo).absolute()
        require(root.is_dir(), "object repository must be a local directory")
        gitdir = root / ".git" if (root / ".git").exists() else root
        self.objects = gitdir / "objects"
        require(self.objects.is_dir(), "ordinary or bare repository required; no gitfiles")
        def direct(path):
            require(not path.is_symlink() and not (getattr(path.lstat(), "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)), "symlinks/reparse points unsupported")
        for path in (root, gitdir, self.objects, *self.objects.parents):
            direct(path)
        def unreadable(error):
            raise error
        for directory, dirs, files in os.walk(self.objects, followlinks=False, onerror=unreadable):
            for name in dirs + files:
                path = Path(directory) / name
                direct(path)
                require(path.is_dir() or path.is_file(), "special object-store files are unsupported")
        require(not any((self.objects / "info" / name).exists()
                        for name in ("alternates", "http-alternates")), "object alternates are unsupported")
        self.control = control
        self.env = {key: value for key, value in os.environ.items()
                    if key in {"PATH", "SystemRoot", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_CONFIG_COUNT="0", GIT_NO_REPLACE_OBJECTS="1",
                        GIT_NO_LAZY_FETCH="1", GIT_OPTIONAL_LOCKS="0",
                        GIT_ALLOW_PROTOCOL="", GIT_TERMINAL_PROMPT="0",
                        GIT_OBJECT_DIRECTORY=str(self.objects))
        self.git = shutil.which("git")
        require(self.git is not None, "Git executable required")

    def run(self, *args):
        result = subprocess.run([self.git, "--no-pager", "--git-dir=" + str(self.control),
                                 "-c", "core.hooksPath=" + os.devnull, *args],
                                cwd=self.control, env=self.env, capture_output=True, timeout=20)
        require(result.returncode == 0, "required local Git object unavailable or invalid")
        return result.stdout

    def read(self, oid, kind):
        require(re.fullmatch("[0-9a-f]{40}", oid) is not None, "full lowercase SHA-1 required")
        require(self.run("cat-file", "-t", oid).strip() == kind.encode(), "wrong Git object type")
        size = int(self.run("cat-file", "-s", oid))
        require(size <= MAX_INTAKE_BYTES, "Git object exceeds intake byte limit")
        data = self.run("cat-file", kind, oid)
        require(len(data) == size, "Git object size changed")
        require(hashlib.sha1(f"{kind} {size}\0".encode() + data).hexdigest() == oid,
                "Git object content does not match its pinned SHA-1")
        return data

    def snapshot(self, commit):
        headers = self.read(commit, "commit").split(b"\n\n", 1)[0].splitlines()
        trees = [line[5:].decode("ascii") for line in headers if line.startswith(b"tree ")]
        require(len(trees) == 1, "exact commit tree required")
        entries, pending, count = {}, [("", trees[0], 0)], 0
        while pending:
            prefix, oid, depth = pending.pop()
            require(depth < 32, "tree nesting exceeds limit")
            raw = self.read(oid, "tree")
            while raw:
                meta, raw = raw.split(b"\0", 1)
                mode, name = meta.split(b" ", 1)
                child, raw = raw[:20].hex(), raw[20:]
                name = name.decode("utf-8")
                require(name not in {"", ".", ".."} and "/" not in name and "\\" not in name,
                        "unsafe tree name")
                path = prefix + name
                require(path not in entries, "duplicate tree path")
                entries[path] = (mode.decode("ascii"), child)
                count += 1
                require(count <= 20000, "tree entry count exceeds limit")
                if mode == b"40000":
                    pending.append((path + "/", child, depth + 1))
        parents = [line[7:].decode("ascii") for line in headers if line.startswith(b"parent ")]
        return entries, parents


def inspect(object_repo, delivery, base, target, json_sha256, review_sha256):
    """Pins come from independent review; no pin generation or workspace reads."""
    for digest in (json_sha256, review_sha256):
        require(re.fullmatch("[0-9a-f]{64}", digest) is not None, "explicit SHA-256 pins required")
    temp_root = Path(tempfile.tempdir or os.environ.get("TMPDIR") or os.environ.get("TEMP")
                     or os.environ.get("TMP") or ("/tmp" if os.name == "posix"
                     else Path.home() / "AppData/Local/Temp")).resolve()
    require(not temp_root.is_relative_to(Path(object_repo).resolve()), "temporary directory must be outside input repository")
    with tempfile.TemporaryDirectory(prefix="pcbknowledge-handoff-", dir=temp_root) as temp:
        control = Path(temp)
        (control / "HEAD").write_text("ref: refs/heads/unused\n", encoding="ascii")
        (control / "refs").mkdir()
        (control / "objects").mkdir()
        objects = Objects(object_repo, control)
        before, _ = objects.snapshot(base)
        after, parents = objects.snapshot(delivery)
        current, _ = objects.snapshot(target)
        require(parents == [base], "delivery must have exactly the supplied base parent")
        for tree in (before, after, current):
            for ancestor in ("knowledge", "knowledge/intake"):
                require(ancestor not in tree or tree[ancestor][0] == "40000", "unsafe intake ancestor")
        # Directory tree IDs necessarily change with an additive pair; compare leaves.
        leaves = lambda tree: {p: v for p, v in tree.items() if v[0] != "40000"}
        old, new = leaves(before), leaves(after)
        changed = {p for p in old.keys() | new.keys() if old.get(p) != new.get(p)}
        jsons = [p for p in changed if re.fullmatch(r"knowledge/intake/[a-z0-9][a-z0-9-]*\.json", p)]
        require(len(jsons) == 1, "exactly one direct intake JSON required")
        path = jsons[0]
        review = path[:-5] + "-review.md"
        require(changed == {path, review}, "exact two-file intake pair required")
        require(all(p in {"knowledge", "knowledge/intake", path, review}
                    for p in before.keys() | after.keys() if before.get(p) != after.get(p)),
                "changes outside the intake pair are forbidden")
        observations, payloads = {}, {}
        for name, pin in ((path, json_sha256), (review, review_sha256)):
            require(name not in before and name not in current, "add-only target/base path collision")
            require(new[name][0] == "100644", "regular nonexecutable blobs required")
            payload = objects.read(new[name][1], "blob")
            payloads[name] = payload.decode("utf-8")
            require(hashlib.sha256(payload).hexdigest() == pin, "independently pinned bytes mismatch")
            observations[name] = {"sha256": pin, "bytes": len(payload), "git_blob": new[name][1]}
        data = _validate_batch(json.loads(payloads[path], object_pairs_hook=_unique_object,
                                          parse_constant=_reject_constant))
        _source_issues(data)
        require(data.get("human_reviewed") is False, "explicit human_reviewed=false required")
    return {"status": "PREFLIGHT_COMPATIBLE_ONLY", "delivery_commit": delivery,
            "delivery_base": base, "target_commit": target, "files": observations,
            "facts": len(data["facts"]), "approval": False, "aggregate": "NOT_RUN",
            "evidence_verification": "NOT_LOCALLY_VERIFIED",
            "limitations": ["No reviewer authentication, source/visual/semantic validation or canonical approval.",
                            "No apply, global replay, CI, package or publication acceptance.",
                            "Target is a pinned observation, not a promise that main remains unchanged."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("object-repo", "delivery", "base", "target", "json-sha256", "review-sha256"):
        parser.add_argument("--" + name, required=True)
    try:
        result = inspect(**vars(parser.parse_args(argv)))
    except (HandoffError, IntakeError, OSError, ValueError, RecursionError,
            subprocess.SubprocessError) as error:
        print(json.dumps({"status": "PREFLIGHT_REJECTED", "error": str(error)}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
