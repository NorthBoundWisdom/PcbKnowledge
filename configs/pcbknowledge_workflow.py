#!/usr/bin/env python3
"""Lightweight FreeCM workflow for the Git-native local editor."""

from __future__ import annotations

import argparse
import compileall
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import webbrowser
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from pcbknowledge.git_native.server import DEFAULT_PORT, create_server  # noqa: E402
from pcbknowledge.git_native.store import KnowledgeRepository, RepositoryError  # noqa: E402


CONFIGURATION_ID = "git-native-local"
RECEIPT_SCHEMA_VERSION = 1
CONFIG_RECEIPT = Path(".freecm/pcbknowledge-config.json")
BUILD_RECEIPT = Path(".freecm/pcbknowledge-build.json")
CONFIG_INPUTS = (
    Path("configs/freecm.commands.jsonc"),
    Path("configs/pcbknowledge_workflow.py"),
    Path("source_roots.lock.jsonc.in"),
)
BUILD_INPUT_FILES = (
    Path("Open PcbKnowledge.command"),
    Path("configs/pcbknowledge_agent.py"),
    Path("configs/pcbknowledge_workflow.py"),
    Path("schemas/knowledge-record.schema.json"),
)
BUILD_INPUT_ROOTS = (
    Path("src/pcbknowledge/git_native"),
    Path("tests/git_native"),
)
IGNORED_SOURCE_NAMES = frozenset({"__pycache__", ".DS_Store"})
PACKAGE_DIRECTORY = Path("build/package")
PACKAGE_FORMAT = "pcbknowledge-git-native-snapshot"
MINIMUM_PYTHON = (3, 11)


class WorkflowError(RuntimeError):
    """A local workflow precondition or receipt is invalid."""


def _display(command: Sequence[str]) -> None:
    print("[pcbknowledge] " + " ".join(command), flush=True)


def _run(command: Sequence[str], *, root: Path = REPO_ROOT) -> None:
    _display(command)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root / "src")
    subprocess.run(list(command), cwd=root, env=environment, check=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WorkflowError(f"{label} is missing or invalid; run FreeCM Config again") from error
    if not isinstance(value, dict):
        raise WorkflowError(f"{label} is invalid; run FreeCM Config again")
    return value


def _input_signature(paths: Iterable[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for relative in sorted(paths, key=lambda item: item.as_posix()):
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise WorkflowError(f"required input is missing or unsafe: {relative}")
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def configuration_signature(root: Path = REPO_ROOT) -> str:
    return _input_signature(CONFIG_INPUTS, root)


def build_inputs(root: Path = REPO_ROOT) -> tuple[Path, ...]:
    paths = list(BUILD_INPUT_FILES)
    for relative_root in BUILD_INPUT_ROOTS:
        directory = root / relative_root
        if directory.is_symlink() or not directory.is_dir():
            raise WorkflowError(f"build input directory is missing or unsafe: {relative_root}")
        for path in directory.rglob("*"):
            relative = path.relative_to(root)
            if any(part in IGNORED_SOURCE_NAMES for part in relative.parts):
                continue
            if path.is_symlink():
                raise WorkflowError(f"build input is an unsafe symlink: {relative}")
            if path.is_file() and path.suffix not in {".pyc", ".pyo"}:
                paths.append(relative)
    return tuple(sorted(set(paths), key=lambda item: item.as_posix()))


def build_signature(root: Path = REPO_ROOT) -> str:
    return _input_signature(build_inputs(root), root)


def _python_identity() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _require_prerequisites(root: Path = REPO_ROOT) -> None:
    if sys.version_info < MINIMUM_PYTHON:
        raise WorkflowError(
            f"Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]} or newer is required"
        )
    git = shutil.which("git")
    if git is None:
        raise WorkflowError("Git is required")
    result = subprocess.run(
        [git, "rev-parse", "--show-toplevel"],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0 or Path(result.stdout.strip()).resolve() != root.resolve():
        raise WorkflowError("run this workflow from the PcbKnowledge Git repository")

    template = _read_json(root / "source_roots.lock.jsonc.in", label="source root template")
    if template.get("dependencies") != {}:
        raise WorkflowError("source_roots.lock.jsonc.in must keep dependencies empty")
    if (root / "source_roots.lock.jsonc").exists():
        raise WorkflowError("an active source-root lock is not allowed before a dependency is approved")


def write_configuration_receipt(root: Path = REPO_ROOT) -> Path:
    return _atomic_json(
        root / CONFIG_RECEIPT,
        {
            "schemaVersion": RECEIPT_SCHEMA_VERSION,
            "configurationId": CONFIGURATION_ID,
            "python": _python_identity(),
            "configurationSignature": configuration_signature(root),
        },
    )


def require_configuration(root: Path = REPO_ROOT) -> dict[str, Any]:
    receipt = _read_json(root / CONFIG_RECEIPT, label="FreeCM Config receipt")
    expected = {
        "schemaVersion": RECEIPT_SCHEMA_VERSION,
        "configurationId": CONFIGURATION_ID,
        "python": _python_identity(),
        "configurationSignature": configuration_signature(root),
    }
    if receipt != expected:
        raise WorkflowError("FreeCM Config inputs changed; run FreeCM Config again")
    return receipt


def write_build_receipt(root: Path = REPO_ROOT) -> Path:
    configuration = require_configuration(root)
    return _atomic_json(
        root / BUILD_RECEIPT,
        {
            "schemaVersion": RECEIPT_SCHEMA_VERSION,
            "configurationSignature": configuration["configurationSignature"],
            "python": _python_identity(),
            "buildSignature": build_signature(root),
        },
    )


def require_build(root: Path = REPO_ROOT) -> dict[str, Any]:
    configuration = require_configuration(root)
    receipt = _read_json(root / BUILD_RECEIPT, label="FreeCM Build receipt")
    expected = {
        "schemaVersion": RECEIPT_SCHEMA_VERSION,
        "configurationSignature": configuration["configurationSignature"],
        "python": _python_identity(),
        "buildSignature": build_signature(root),
    }
    if receipt != expected:
        raise WorkflowError("editor source changed; run FreeCM Build again")
    return receipt


def _validate_knowledge(root: Path = REPO_ROOT) -> int:
    repository = KnowledgeRepository(root)
    repository.ensure_layout()
    records = repository.validate_all(require_canonical=True)
    print(f"[pcbknowledge] validated {len(records)} knowledge records", flush=True)
    return len(records)


def _run_checks(root: Path = REPO_ROOT) -> None:
    compile_targets = [
        "src/pcbknowledge/git_native",
        "configs/pcbknowledge_workflow.py",
        "configs/pcbknowledge_agent.py",
        "tests/git_native",
    ]
    print("[pcbknowledge] compile local editor", flush=True)
    if not compileall.compile_dir(
        str(root / "src/pcbknowledge/git_native"), quiet=1, force=True
    ):
        raise WorkflowError("Python compilation failed")
    for relative in compile_targets[1:3]:
        if not compileall.compile_file(str(root / relative), quiet=1, force=True):
            raise WorkflowError(f"Python compilation failed: {relative}")
    _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests/git_native",
            "-t",
            ".",
            "-v",
        ],
        root=root,
    )
    _validate_knowledge(root)


def cmd_config() -> int:
    _require_prerequisites()
    repository = KnowledgeRepository(REPO_ROOT)
    repository.ensure_layout()
    receipt = write_configuration_receipt()
    print(f"[pcbknowledge] ready: {receipt.relative_to(REPO_ROOT)}", flush=True)
    print("[pcbknowledge] no containers, services, accounts or downloads are required", flush=True)
    return 0


def cmd_build() -> int:
    _require_prerequisites()
    require_configuration()
    _run_checks()
    receipt = write_build_receipt()
    print(f"[pcbknowledge] build receipt: {receipt.relative_to(REPO_ROOT)}", flush=True)
    return 0


def cmd_test() -> int:
    _require_prerequisites()
    require_configuration()
    _run_checks()
    _run(["git", "diff", "--check"], root=REPO_ROOT)
    return 0


def _open_editor(url: str) -> bool:
    if os.environ.get("CI") or os.environ.get("PCBKNOWLEDGE_DISABLE_BROWSER_OPEN") == "1":
        return False
    try:
        return bool(webbrowser.open(url, new=2, autoraise=True))
    except (OSError, webbrowser.Error):
        return False


def cmd_run(*, port: int, no_browser: bool) -> int:
    _require_prerequisites()
    require_build()
    _validate_knowledge()
    try:
        server = create_server(REPO_ROOT, port)
    except OSError as error:
        raise WorkflowError(
            f"cannot start the editor on 127.0.0.1:{port}; close the program using that port"
        ) from error
    url = f"http://127.0.0.1:{server.server_port}"
    print("[pcbknowledge] local editor ready", flush=True)
    print(f"[pcbknowledge] open: {url}", flush=True)
    print("[pcbknowledge] no login or password", flush=True)
    print("[pcbknowledge] Ctrl+C closes the editor; saved files stay in the Git worktree", flush=True)
    if not no_browser and not _open_editor(url):
        print("[pcbknowledge] the browser did not open automatically; use the URL above", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\n[pcbknowledge] editor stopped", flush=True)
        return 130
    finally:
        server.server_close()
    return 0


def cmd_open(*, port: int, no_browser: bool) -> int:
    """Prepare an unconfigured checkout once, then open the local editor."""

    _require_prerequisites()
    try:
        require_build()
    except WorkflowError:
        print("[pcbknowledge] first use or editor source changed; running local checks", flush=True)
        cmd_config()
        cmd_build()
    return cmd_run(port=port, no_browser=no_browser)


def package_files(root: Path = REPO_ROOT) -> tuple[Path, ...]:
    repository = KnowledgeRepository(root)
    records = repository.validate_all(require_canonical=True)
    paths = {Path("schemas/knowledge-record.schema.json")}
    for record in records:
        paths.add(repository.record_path(record.id).relative_to(repository.root))
        if record.evidence.path is not None:
            paths.add(Path(record.evidence.path))
    return tuple(sorted(paths, key=lambda item: item.as_posix()))


def _snapshot_manifest(files: Sequence[Path], root: Path) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "format": PACKAGE_FORMAT,
        "files": [
            {
                "path": relative.as_posix(),
                "sha256": _sha256(root / relative),
                "byteSize": (root / relative).stat().st_size,
            }
            for relative in files
        ],
    }


def create_package(root: Path = REPO_ROOT) -> Path:
    require_build(root)
    files = package_files(root)
    manifest = _snapshot_manifest(files, root)
    manifest_payload = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    identity = hashlib.sha256(manifest_payload).hexdigest()[:16]
    output_directory = root / PACKAGE_DIRECTORY
    output_directory.mkdir(parents=True, exist_ok=True)
    output = output_directory / f"PcbKnowledge_{identity}.zip"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output_directory
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for relative in files:
                info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, (root / relative).read_bytes(), compresslevel=9)
            manifest_info = zipfile.ZipInfo(
                "MANIFEST.json", date_time=(1980, 1, 1, 0, 0, 0)
            )
            manifest_info.compress_type = zipfile.ZIP_DEFLATED
            manifest_info.external_attr = 0o100644 << 16
            archive.writestr(manifest_info, manifest_payload, compresslevel=9)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    digest = _sha256(output)
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n", encoding="ascii", newline="\n"
    )
    return output


def cmd_package() -> int:
    _require_prerequisites()
    output = create_package()
    print(f"[pcbknowledge] data snapshot: {output.relative_to(REPO_ROOT)}", flush=True)
    print(f"[pcbknowledge] sha256: {_sha256(output)}", flush=True)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PcbKnowledge local FreeCM workflow")
    parser.add_argument(
        "action", choices=("config", "build", "run", "open", "test", "package")
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.port < 1 or arguments.port > 65535:
        parser.error("--port must be between 1 and 65535")
    if arguments.action not in {"run", "open"} and (
        arguments.no_browser or arguments.port != DEFAULT_PORT
    ):
        parser.error("--port and --no-browser are only valid for run/open")
    return arguments


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        if arguments.action == "config":
            return cmd_config()
        if arguments.action == "build":
            return cmd_build()
        if arguments.action == "test":
            return cmd_test()
        if arguments.action == "package":
            return cmd_package()
        if arguments.action == "open":
            return cmd_open(port=arguments.port, no_browser=arguments.no_browser)
        return cmd_run(port=arguments.port, no_browser=arguments.no_browser)
    except (WorkflowError, RepositoryError) as error:
        print(f"pcbknowledge: {error}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as error:
        return error.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
