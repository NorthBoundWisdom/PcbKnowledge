from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from configs import pcbknowledge_workflow as workflow
from configs import validate_freecm_repo_commands as validator


def _write_configuration_inputs(repo_root: Path) -> None:
    for index, relative_path in enumerate(workflow.CONFIG_INPUTS):
        path = repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"input-{index}\n", encoding="utf-8")


def _write_configuration_secret_outputs(repo_root: Path) -> None:
    for relative_path in workflow.CONFIG_SECRET_OUTPUTS:
        path = repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("secret\n", encoding="utf-8")
        path.chmod(0o600)


def test_workflow_environment_owns_isolated_compose_settings() -> None:
    environment = workflow.workflow_environment(
        {
            "PATH": "/usr/bin",
            "COMPOSE_PROJECT_NAME": "caller-project",
            "PCBKNOWLEDGE_HTTP_PORT": "8080",
        }
    )

    assert environment["PATH"] == "/usr/bin"
    assert environment["COMPOSE_PROJECT_NAME"] == "pcbknowledge-freecm"
    assert environment["PCBKNOWLEDGE_HTTP_PORT"] == "18080"
    assert environment["PCBKNOWLEDGE_KEYCLOAK_PORT"] == "18081"


def test_configuration_receipt_is_bound_to_all_declared_inputs(tmp_path: Path) -> None:
    _write_configuration_inputs(tmp_path)
    _write_configuration_secret_outputs(tmp_path)
    receipt_path = workflow.write_configuration_receipt(tmp_path)

    workflow.require_configuration(tmp_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["configurationId"] == workflow.CONFIGURATION_ID
    assert receipt["composeProject"] == "pcbknowledge-freecm"

    changed_input = tmp_path / workflow.CONFIG_INPUTS[0]
    changed_input.write_text("changed\n", encoding="utf-8")
    with pytest.raises(workflow.WorkflowError, match="inputs changed"):
        workflow.require_configuration(tmp_path)


def test_configuration_receipt_is_required(tmp_path: Path) -> None:
    _write_configuration_inputs(tmp_path)

    with pytest.raises(workflow.WorkflowError, match="configuration is missing"):
        workflow.require_configuration(tmp_path)


def test_configuration_rejects_non_owner_only_secret_output(tmp_path: Path) -> None:
    _write_configuration_inputs(tmp_path)
    _write_configuration_secret_outputs(tmp_path)
    workflow.write_configuration_receipt(tmp_path)
    unsafe_output = tmp_path / workflow.CONFIG_SECRET_OUTPUTS[0]
    unsafe_output.chmod(0o644)

    with pytest.raises(workflow.WorkflowError, match="not owner-only"):
        workflow.require_configuration(tmp_path)


def test_manifest_readiness_matches_workflow_contract() -> None:
    manifest = json.loads((workflow.REPO_ROOT / "configs/freecm.commands.jsonc").read_text())
    readiness = manifest["commands"]["config"][0]["readiness"]

    assert readiness["inputs"] == [str(path) for path in workflow.CONFIG_INPUTS]
    assert readiness["outputs"] == [
        str(workflow.CONFIG_RECEIPT),
        *(str(path) for path in workflow.CONFIG_SECRET_OUTPUTS),
    ]


def test_package_uses_only_repository_owned_images() -> None:
    assert workflow.package_image_names() == (
        "pcbknowledge-freecm-api:latest",
        "pcbknowledge-freecm-worker:latest",
        "pcbknowledge-freecm-web:latest",
        "pcbknowledge-freecm-migrate:latest",
        "pcbknowledge-freecm-storage-init:latest",
    )


def test_package_platform_comes_from_built_images() -> None:
    metadata = [
        {"Os": "linux", "Architecture": "arm64"},
        {"Os": "linux", "Architecture": "arm64"},
    ]

    assert workflow._image_platform(metadata) == "linux-arm64"

    with pytest.raises(workflow.WorkflowError, match="do not share"):
        workflow._image_platform([*metadata, {"Os": "linux", "Architecture": "amd64"}])


def test_run_always_stops_its_isolated_compose_project(monkeypatch: pytest.MonkeyPatch) -> None:
    checked: list[tuple[str, ...]] = []
    unchecked: list[tuple[str, ...]] = []

    monkeypatch.setattr(workflow, "require_configuration", lambda: None)
    monkeypatch.setattr(workflow, "require_docker", lambda _environment: None)
    monkeypatch.setattr(workflow, "workflow_environment", lambda: {"TEST": "1"})
    monkeypatch.setattr(
        workflow,
        "_run_checked",
        lambda command, *, environment: checked.append(tuple(command)),
    )

    def run_unchecked(command: list[str], *, environment: object) -> int:
        del environment
        unchecked.append(tuple(command))
        return 0

    monkeypatch.setattr(workflow, "_run_unchecked", run_unchecked)

    assert workflow.cmd_run() == 0
    assert checked == [("/bin/sh", "deploy/scripts/dev-up.sh", "--skip-config")]
    assert unchecked[0][:4] == ("docker", "compose", "logs", "--follow")
    assert unchecked[-1] == ("/bin/sh", "deploy/scripts/dev-down.sh")


def test_validator_fails_closed_when_submodule_is_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert validator.validate_repo_commands(tmp_path) == 1
    assert "git submodule update --init" in capsys.readouterr().err


def test_validator_rebuilds_and_runs_the_pinned_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    extension_root = tmp_path / "FreeCM" / "vscode-extension"
    (extension_root / "node_modules").mkdir(parents=True)
    (extension_root / "package.json").write_text("{}\n", encoding="utf-8")
    validator_path = extension_root / "out" / "validateRepoCommands.js"
    validator_path.parent.mkdir()
    validator_path.write_text("// generated\n", encoding="utf-8")
    calls: list[tuple[list[str], Path]] = []

    monkeypatch.setattr(
        "configs.validate_freecm_repo_commands.shutil.which",
        lambda executable: f"/tools/{executable}",
    )

    def run(command: list[str], *, cwd: Path, check: bool) -> SimpleNamespace:
        assert check is False
        calls.append((command, cwd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("configs.validate_freecm_repo_commands.subprocess.run", run)

    assert validator.validate_repo_commands(tmp_path) == 0
    assert calls == [
        (
            ["/tools/npm", "run", "compile", "--", "--pretty", "false"],
            extension_root,
        ),
        (
            ["/tools/node", str(validator_path), "--preview", str(tmp_path)],
            tmp_path,
        ),
    ]


def test_workflow_main_preserves_subprocess_failure_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail() -> int:
        raise subprocess.CalledProcessError(7, ["docker", "compose"])

    monkeypatch.setattr(workflow, "cmd_build", fail)

    assert workflow.main(["build"]) == 7
