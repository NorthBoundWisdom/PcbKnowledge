"""Knowledge-workspace identity, schema pinning, and initialization."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


WORKSPACE_MANIFEST_PATH = Path("pcbknowledge.workspace.json")
WORKSPACE_GITIGNORE_PATH = Path(".gitignore")
WORKSPACE_GITIGNORE_RULE = "/.pcbknowledge/"
WORKSPACE_FORMAT = "pcbknowledge-workspace-v1"
SCHEMA_CONTRACT = "typed-v1"
CREATED_WITH = "PcbKnowledge"
MAX_MANIFEST_BYTES = 64 * 1024
MAX_SCHEMA_BYTES = 1_000_000
MAX_GITIGNORE_BYTES = 64 * 1024
SCHEMA_PATHS = (
    Path("schemas/source-record.schema.json"),
    Path("schemas/entity-record.schema.json"),
    Path("schemas/fact-record.schema.json"),
)
AUTHORITY_DIRECTORIES = (
    Path("knowledge/sources"),
    Path("knowledge/entities"),
    Path("knowledge/facts"),
    Path("evidence/sha256"),
)
PLACEHOLDER_PATHS = tuple(path / ".gitkeep" for path in AUTHORITY_DIRECTORIES)


class WorkspaceError(RuntimeError):
    """The selected knowledge workspace is missing, ambiguous, or inconsistent."""


@dataclass(frozen=True, slots=True)
class WorkspaceManifest:
    format: str
    schema_contract: str
    schema_digest: str
    created_with: str

    def validate(self) -> "WorkspaceManifest":
        if self.format != WORKSPACE_FORMAT:
            raise WorkspaceError(f"unsupported workspace format: {self.format!r}")
        if self.schema_contract != SCHEMA_CONTRACT:
            raise WorkspaceError(
                f"unsupported workspace schema contract: {self.schema_contract!r}"
            )
        if (
            len(self.schema_digest) != 64
            or any(character not in "0123456789abcdef" for character in self.schema_digest)
        ):
            raise WorkspaceError("workspace schema_digest must be lowercase SHA-256")
        if self.created_with != CREATED_WITH:
            raise WorkspaceError(
                f"unsupported workspace creator marker: {self.created_with!r}"
            )
        return self

    def to_dict(self) -> dict[str, str]:
        return {
            "format": self.format,
            "schema_contract": self.schema_contract,
            "schema_digest": self.schema_digest,
            "created_with": self.created_with,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"

    @classmethod
    def from_json(cls, payload: str) -> "WorkspaceManifest":
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as error:
            raise WorkspaceError("workspace manifest is not valid JSON") from error
        if not isinstance(value, dict):
            raise WorkspaceError("workspace manifest must be a JSON object")
        expected = {"format", "schema_contract", "schema_digest", "created_with"}
        if set(value) != expected:
            raise WorkspaceError("workspace manifest has unsupported or missing fields")
        if not all(isinstance(value[key], str) for key in expected):
            raise WorkspaceError("workspace manifest fields must be strings")
        return cls(
            format=value["format"],
            schema_contract=value["schema_contract"],
            schema_digest=value["schema_digest"],
            created_with=value["created_with"],
        ).validate()


@dataclass(frozen=True, slots=True)
class WorkspaceValidation:
    root: Path
    manifest: WorkspaceManifest
    ref: str | None = None
    commit: str | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceInitialization:
    validation: WorkspaceValidation
    replayed: bool


# Hashing exact schema bytes through their deterministic Git blob identity keeps
# the workspace digest independent of filesystem metadata and line-ending APIs.
def _git_blob_oid(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def schema_digest_from_payloads(payloads: Mapping[str, bytes]) -> str:
    expected = {path.as_posix() for path in SCHEMA_PATHS}
    if set(payloads) != expected:
        raise WorkspaceError("typed workspace schema set is incomplete")
    digest = hashlib.sha256()
    for relative in sorted(expected):
        payload = payloads[relative]
        if len(payload) > MAX_SCHEMA_BYTES:
            raise WorkspaceError(f"workspace schema exceeds size limit: {relative}")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_git_blob_oid(payload).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _read_regular_file(path: Path, *, label: str, maximum_bytes: int) -> bytes:
    try:
        stat = path.lstat()
    except FileNotFoundError as error:
        raise WorkspaceError(f"{label} is missing: {path}") from error
    if path.is_symlink() or not path.is_file():
        raise WorkspaceError(f"{label} is not a regular file: {path}")
    if stat.st_size > maximum_bytes:
        raise WorkspaceError(f"{label} exceeds {maximum_bytes} bytes: {path}")
    return path.read_bytes()


def schema_payloads(root: Path) -> dict[str, bytes]:
    return {
        relative.as_posix(): _read_regular_file(
            root / relative,
            label="workspace schema",
            maximum_bytes=MAX_SCHEMA_BYTES,
        )
        for relative in SCHEMA_PATHS
    }


def schema_digest(root: Path) -> str:
    return schema_digest_from_payloads(schema_payloads(root))


def _git_root(root: Path) -> Path:
    resolved = root.resolve()
    if not resolved.is_dir():
        raise WorkspaceError(f"workspace directory does not exist: {resolved}")
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=resolved,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise WorkspaceError(f"workspace is not a Git repository: {resolved}")
    discovered = Path(result.stdout.strip()).resolve()
    if discovered != resolved:
        raise WorkspaceError(
            f"workspace must be a Git repository root, got nested path: {resolved}"
        )
    return resolved


def _load_manifest_bytes(payload: bytes, *, label: str) -> WorkspaceManifest:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise WorkspaceError(f"{label} is not UTF-8") from error
    manifest = WorkspaceManifest.from_json(text)
    if payload != manifest.canonical_json().encode("utf-8"):
        raise WorkspaceError(f"{label} is not canonical JSON")
    return manifest


def _validate_gitignore_payload(payload: bytes, *, label: str) -> None:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise WorkspaceError(f"{label} is not UTF-8") from error
    if WORKSPACE_GITIGNORE_RULE not in {line.strip() for line in text.splitlines()}:
        raise WorkspaceError(
            f"{label} must ignore {WORKSPACE_GITIGNORE_RULE} derived runtime state"
        )


def validate_workspace_gitignore(root: Path) -> None:
    """Require derived runtime state to be ignored for a new active workspace."""

    resolved = _git_root(root)
    payload = _read_regular_file(
        resolved / WORKSPACE_GITIGNORE_PATH,
        label="workspace .gitignore",
        maximum_bytes=MAX_GITIGNORE_BYTES,
    )
    _validate_gitignore_payload(payload, label="workspace .gitignore")


def validate_workspace(root: Path) -> WorkspaceValidation:
    resolved = _git_root(root)
    manifest_payload = _read_regular_file(
        resolved / WORKSPACE_MANIFEST_PATH,
        label="workspace manifest",
        maximum_bytes=MAX_MANIFEST_BYTES,
    )
    manifest = _load_manifest_bytes(manifest_payload, label="workspace manifest")
    actual_digest = schema_digest(resolved)
    if manifest.schema_digest != actual_digest:
        raise WorkspaceError(
            "workspace schema digest does not match the pinned schema snapshot"
        )

    for relative in AUTHORITY_DIRECTORIES:
        path = resolved / relative
        if path.is_symlink() or not path.is_dir():
            raise WorkspaceError(f"workspace directory is missing or unsafe: {relative}")

    legacy = resolved / "knowledge/records"
    if legacy.exists():
        if legacy.is_symlink() or not legacy.is_dir():
            raise WorkspaceError("retired knowledge/records path is unsafe")
        unexpected = [entry for entry in legacy.iterdir() if entry.name != ".gitkeep"]
        if unexpected:
            raise WorkspaceError("retired knowledge/records authority is not allowed")

    return WorkspaceValidation(root=resolved, manifest=manifest)


def _git_output(root: Path, *arguments: str, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise WorkspaceError(detail or f"git {' '.join(arguments)} failed")
    return result.stdout


def validate_workspace_ref(root: Path, ref: str = "HEAD") -> WorkspaceValidation:
    resolved = _git_root(root)
    commit = _git_output(resolved, "rev-parse", "--verify", f"{ref}^{{commit}}")
    commit_id = commit.decode("ascii").strip()
    manifest_payload = _git_output(
        resolved, "show", f"{commit_id}:{WORKSPACE_MANIFEST_PATH.as_posix()}"
    )
    if len(manifest_payload) > MAX_MANIFEST_BYTES:
        raise WorkspaceError("published workspace manifest exceeds size limit")
    manifest = _load_manifest_bytes(
        manifest_payload, label=f"workspace manifest at {ref}"
    )

    payloads: dict[str, bytes] = {}
    for relative in SCHEMA_PATHS:
        payload = _git_output(resolved, "show", f"{commit_id}:{relative.as_posix()}")
        if len(payload) > MAX_SCHEMA_BYTES:
            raise WorkspaceError(
                f"published workspace schema exceeds size limit: {relative}"
            )
        payloads[relative.as_posix()] = payload
    actual_digest = schema_digest_from_payloads(payloads)
    if manifest.schema_digest != actual_digest:
        raise WorkspaceError(
            f"workspace schema digest does not match the schema snapshot at {ref}"
        )
    return WorkspaceValidation(
        root=resolved,
        manifest=manifest,
        ref=ref,
        commit=commit_id,
    )


def _working_tree_is_clean(root: Path) -> bool:
    return not _git_output(
        root, "status", "--porcelain", "--untracked-files=all"
    ).strip()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def initialize_workspace(
    target: Path,
    *,
    schema_source_root: Path,
    init_git: bool = False,
) -> WorkspaceInitialization:
    target = target.expanduser()
    if not target.exists():
        if not init_git:
            raise WorkspaceError(
                "workspace target does not exist; create a Git repository first or use --init-git"
            )
        target.mkdir(parents=True)
    if not target.is_dir():
        raise WorkspaceError(f"workspace target is not a directory: {target}")

    try:
        resolved = _git_root(target)
    except WorkspaceError:
        if not init_git:
            raise
        if any(target.iterdir()):
            raise WorkspaceError(
                "--init-git requires a missing or empty target directory"
            )
        subprocess.run(["git", "init", "-q", str(target)], check=True)
        resolved = _git_root(target)

    source_payloads = schema_payloads(schema_source_root.resolve())
    desired_digest = schema_digest_from_payloads(source_payloads)
    manifest_path = resolved / WORKSPACE_MANIFEST_PATH

    if manifest_path.exists():
        validation = validate_workspace(resolved)
        if validation.manifest.schema_digest != desired_digest:
            raise WorkspaceError(
                "existing workspace uses a different schema snapshot; use an explicit schema-upgrade workflow"
            )
        if any(
            (resolved / relative).read_bytes() != source_payloads[relative.as_posix()]
            for relative in SCHEMA_PATHS
        ):
            raise WorkspaceError("existing workspace schema bytes differ from the requested contract")
        return WorkspaceInitialization(validation=validation, replayed=True)

    if not _working_tree_is_clean(resolved):
        raise WorkspaceError("workspace initialization requires a clean Git working tree")

    schema_dir = resolved / "schemas"
    if schema_dir.exists():
        if schema_dir.is_symlink() or not schema_dir.is_dir():
            raise WorkspaceError("workspace schemas path is unsafe")
        if any(schema_dir.iterdir()):
            raise WorkspaceError("workspace schemas directory is not empty")

    legacy = resolved / "knowledge/records"
    if legacy.exists() and any(legacy.iterdir()):
        raise WorkspaceError("retired knowledge/records content blocks workspace initialization")

    for relative in AUTHORITY_DIRECTORIES:
        directory = resolved / relative
        if directory.exists():
            if directory.is_symlink() or not directory.is_dir():
                raise WorkspaceError(f"workspace path is unsafe: {relative}")
            entries = list(directory.iterdir())
            if any(entry.name != ".gitkeep" for entry in entries):
                raise WorkspaceError(
                    f"workspace authority directory is not empty: {relative}"
                )

    created: list[Path] = []
    try:
        gitignore_path = resolved / WORKSPACE_GITIGNORE_PATH
        if gitignore_path.exists():
            payload = _read_regular_file(
                gitignore_path,
                label="workspace .gitignore",
                maximum_bytes=MAX_GITIGNORE_BYTES,
            )
            _validate_gitignore_payload(payload, label="workspace .gitignore")
        else:
            _atomic_write(
                gitignore_path,
                (WORKSPACE_GITIGNORE_RULE + "\n").encode("utf-8"),
            )
            created.append(gitignore_path)

        for relative in SCHEMA_PATHS:
            destination = resolved / relative
            if destination.exists():
                raise WorkspaceError(f"workspace file already exists: {relative}")
            _atomic_write(destination, source_payloads[relative.as_posix()])
            created.append(destination)

        for relative in PLACEHOLDER_PATHS:
            destination = resolved / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                _atomic_write(destination, b"\n")
                created.append(destination)

        manifest = WorkspaceManifest(
            format=WORKSPACE_FORMAT,
            schema_contract=SCHEMA_CONTRACT,
            schema_digest=desired_digest,
            created_with=CREATED_WITH,
        ).validate()
        _atomic_write(manifest_path, manifest.canonical_json().encode("utf-8"))
        created.append(manifest_path)
        validation = validate_workspace(resolved)
    except BaseException:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise

    return WorkspaceInitialization(validation=validation, replayed=False)
