from __future__ import annotations

import json
import signal
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from configs import pcbknowledge_workflow as workflow
from configs import test_local_stack_acceptance as acceptance
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


def _write_build_inputs(repo_root: Path) -> None:
    for index, relative_path in enumerate(workflow.BUILD_INPUT_FILES):
        path = repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"build-input-{index}\n", encoding="utf-8")
    for index, relative_root in enumerate(workflow.BUILD_INPUT_ROOTS):
        root = repo_root / relative_root
        root.mkdir(parents=True, exist_ok=True)
        (root / "owned-source.txt").write_text(f"build-root-{index}\n", encoding="utf-8")


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
    configuration = manifest["commands"]["config"][0]
    readiness = configuration["readiness"]

    assert readiness["inputs"] == [str(path) for path in workflow.CONFIG_INPUTS]
    assert readiness["outputs"] == [
        str(workflow.CONFIG_RECEIPT),
        *(str(path) for path in workflow.CONFIG_SECRET_OUTPUTS),
    ]
    assert configuration["defaults"]["build"] == "prepare-runtime"
    assert configuration["defaults"]["run"] == "start-built-apps"


def test_freecm_curator_origin_is_an_exact_oidc_redirect() -> None:
    origin = f"http://localhost:{workflow.FREECM_ENVIRONMENT['PCBKNOWLEDGE_HTTP_PORT']}"
    expected_callback = f"{origin}/auth/callback"
    expected_logout_callback = f"{origin}/auth/logout/callback"
    definitions = (
        workflow.REPO_ROOT / "deploy/keycloak/pcbknowledge-curator-client.json",
        workflow.REPO_ROOT / "deploy/keycloak/pcbknowledge-realm.template.json",
    )

    for definition in definitions:
        payload = json.loads(definition.read_text(encoding="utf-8"))
        if "clients" in payload:
            client = next(
                item
                for item in payload["clients"]
                if item["clientId"] == "pcbknowledge-curator-web"
            )
        else:
            client = payload

        assert expected_callback in client["redirectUris"]
        assert origin in client["webOrigins"]
        assert expected_logout_callback in client["attributes"]["post.logout.redirect.uris"].split(
            "##"
        )


def test_runtime_receipt_binds_configuration_images_and_ready_infrastructure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_configuration_inputs(tmp_path)
    _write_build_inputs(tmp_path)
    image_ids = {
        service: f"sha256:{index}" for index, service in enumerate(workflow.BUILD_SERVICES)
    }
    readiness_checks: list[dict[str, str]] = []
    monkeypatch.setattr(workflow, "_runtime_image_ids", lambda _environment: image_ids)
    monkeypatch.setattr(
        workflow,
        "_require_infrastructure_ready",
        lambda environment: readiness_checks.append(dict(environment)),
    )

    receipt_path = workflow.write_runtime_receipt({"TEST": "1"}, tmp_path)
    workflow.require_runtime_prepared({"TEST": "1"}, tmp_path)

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["images"] == image_ids
    assert receipt["configurationSignature"] == workflow.configuration_signature(tmp_path)
    assert receipt["buildInputSignature"] == workflow.build_input_signature(tmp_path)
    assert readiness_checks == [{"TEST": "1"}]

    monkeypatch.setattr(
        workflow,
        "_runtime_image_ids",
        lambda _environment: {**image_ids, "api": "sha256:changed"},
    )
    with pytest.raises(workflow.WorkflowError, match="images changed"):
        workflow.require_runtime_prepared({"TEST": "1"}, tmp_path)


def test_runtime_receipt_rejects_source_or_migration_changes_without_rebuilding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_configuration_inputs(tmp_path)
    _write_build_inputs(tmp_path)
    image_ids = {
        service: f"sha256:{index}" for index, service in enumerate(workflow.BUILD_SERVICES)
    }
    monkeypatch.setattr(workflow, "_runtime_image_ids", lambda _environment: image_ids)
    monkeypatch.setattr(workflow, "_require_infrastructure_ready", lambda _environment: None)
    workflow.write_runtime_receipt({"TEST": "1"}, tmp_path)

    source = tmp_path / "src" / "owned-source.txt"
    source.write_text("changed after Build\n", encoding="utf-8")
    with pytest.raises(workflow.WorkflowError, match="build inputs changed"):
        workflow.require_runtime_prepared({"TEST": "1"}, tmp_path)

    source.write_text("build-root-5\n", encoding="utf-8")
    ignored_cache = source.parent / "__pycache__" / "ignored.pyc"
    ignored_cache.parent.mkdir()
    ignored_cache.write_bytes(b"not a Docker build input")
    workflow.require_runtime_prepared({"TEST": "1"}, tmp_path)

    nginx_configuration = tmp_path / "deploy/docker/nginx.conf"
    original_nginx_configuration = nginx_configuration.read_text(encoding="utf-8")
    nginx_configuration.write_text("changed after Build\n", encoding="utf-8")
    with pytest.raises(workflow.WorkflowError, match="build inputs changed"):
        workflow.require_runtime_prepared({"TEST": "1"}, tmp_path)
    nginx_configuration.write_text(original_nginx_configuration, encoding="utf-8")

    migration = tmp_path / "migrations" / "new_revision.py"
    migration.write_text("revision = 'new'\n", encoding="utf-8")
    with pytest.raises(workflow.WorkflowError, match="build inputs changed"):
        workflow.require_runtime_prepared({"TEST": "1"}, tmp_path)


def test_run_requires_an_explicit_prepared_runtime(tmp_path: Path) -> None:
    with pytest.raises(workflow.WorkflowError, match="run FreeCM Build before Run"):
        workflow.require_runtime_prepared({"TEST": "1"}, tmp_path)


def test_prepare_runtime_owns_slow_setup_and_creates_stopped_apps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checked: list[tuple[str, ...]] = []
    built: list[dict[str, str]] = []
    environment = {"TEST": "1"}
    monkeypatch.setattr(
        workflow,
        "_run_checked",
        lambda command, *, environment: checked.append(tuple(command)),
    )
    monkeypatch.setattr(
        workflow,
        "_build_images",
        lambda environment: built.append(dict(environment)),
    )

    workflow._prepare_runtime(environment)

    assert built == [environment]
    assert checked[0] == ("docker", "compose", "stop", *workflow.APPLICATION_SERVICES)
    assert (
        "docker",
        "compose",
        "up",
        "--detach",
        "--wait",
        "--force-recreate",
        "postgres",
    ) in checked
    assert (
        "docker",
        "compose",
        "up",
        "--detach",
        "--wait",
        "--force-recreate",
        "seaweedfs",
    ) in checked
    assert (
        "docker",
        "compose",
        "up",
        "--detach",
        "--wait",
        "--force-recreate",
        "keycloak",
    ) in checked
    assert (
        "docker",
        "compose",
        "up",
        "--detach",
        "--force-recreate",
        "otel-collector",
        "prometheus",
        "grafana",
    ) in checked
    migration = ("docker", "compose", "run", "--rm", "migrate")
    reconciliation = ("docker", "compose", "run", "--rm", "postgres-reconcile")
    identity_bootstrap = ("/bin/sh", "deploy/scripts/bootstrap-local-development.sh")
    storage_initialization = ("docker", "compose", "run", "--rm", "storage-init")
    assert checked.index(migration) < checked.index(reconciliation)
    assert checked.index(reconciliation) < checked.index(identity_bootstrap)
    assert checked.index(identity_bootstrap) < checked.index(storage_initialization)
    assert checked[-1] == (
        "docker",
        "compose",
        "up",
        "--no-start",
        "--no-build",
        "--no-deps",
        *workflow.APPLICATION_SERVICES,
    )


def test_build_verifies_the_privileged_backend_entrypoint_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checked: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        workflow,
        "_run_checked",
        lambda command, *, environment: checked.append(tuple(command)),
    )

    workflow._build_images({"TEST": "1"})

    assert checked[0] == (
        "docker",
        "compose",
        "--profile",
        "tools",
        "build",
        *workflow.BUILD_SERVICES,
    )
    assert checked[1][:7] == (
        "docker",
        "run",
        "--rm",
        "--entrypoint",
        "/bin/sh",
        "pcbknowledge-freecm-api:latest",
        "-ec",
    )
    boundary = checked[1][7]
    assert "/usr/local/bin/pcbknowledge-backend-entrypoint" in boundary
    assert "--reuid=pcbknowledge" in boundary
    assert "/workspace/.venv/bin/tr" in boundary
    assert "untrusted-runtime-tool-executed" in boundary


def test_package_uses_only_repository_owned_images() -> None:
    assert workflow.package_image_names() == (
        "pcbknowledge-freecm-api:latest",
        "pcbknowledge-freecm-worker:latest",
        "pcbknowledge-freecm-verifier:latest",
        "pcbknowledge-freecm-web:latest",
        "pcbknowledge-freecm-migrate:latest",
        "pcbknowledge-freecm-storage-init:latest",
    )


def test_package_archives_the_prepared_images_without_rebuilding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment = {"TEST": "1"}
    prepared: list[dict[str, str]] = []
    image_names = workflow.package_image_names()
    image_metadata = [
        {
            "Id": f"sha256:{index}",
            "RepoTags": [image_name],
            "Os": "linux",
            "Architecture": "arm64",
        }
        for index, image_name in enumerate(image_names)
    ]

    monkeypatch.setattr(workflow, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(workflow, "require_configuration", lambda: None)
    monkeypatch.setattr(workflow, "require_docker", lambda _environment: None)
    monkeypatch.setattr(workflow, "workflow_environment", lambda: environment)
    monkeypatch.setattr(
        workflow,
        "require_runtime_prepared",
        lambda actual: prepared.append(dict(actual)),
    )
    monkeypatch.setattr(
        workflow,
        "_build_images",
        lambda _environment: pytest.fail("Package must not rebuild prepared images"),
    )
    monkeypatch.setattr(
        workflow,
        "_capture",
        lambda command, *, environment: json.dumps(image_metadata),
    )
    monkeypatch.setattr(workflow, "_working_tree_identity", lambda _environment: ("abc123", False))

    def create_archive(
        images: tuple[str, ...],
        output_path: Path,
        *,
        environment: dict[str, str],
    ) -> None:
        assert images == image_names
        assert environment == {"TEST": "1"}
        output_path.write_bytes(b"prepared images")

    monkeypatch.setattr(workflow, "_create_image_archive", create_archive)

    assert workflow.cmd_package() == 0
    assert prepared == [environment]


def test_test_action_checks_deployment_wiring_before_container_suites(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checked: list[tuple[str, ...]] = []
    monkeypatch.setattr(workflow, "require_configuration", lambda: None)
    monkeypatch.setattr(workflow, "require_docker", lambda _environment: None)
    monkeypatch.setattr(workflow, "workflow_environment", lambda: {"TEST": "1"})
    monkeypatch.setattr(
        workflow,
        "_run_checked",
        lambda command, *, environment: checked.append(tuple(command)),
    )

    assert workflow.cmd_test() == 0
    assert checked[0] == (
        "/bin/sh",
        "deploy/scripts/test-verifier-deployment-wiring.sh",
    )
    assert checked[1] == (
        "docker",
        "compose",
        "--profile",
        "tools",
        "build",
        *workflow.TEST_SERVICES,
    )
    assert checked[2:] == [
        (
            "docker",
            "compose",
            "--profile",
            "tools",
            "run",
            "--rm",
            "--no-deps",
            service,
        )
        for service in workflow.TEST_SERVICES
    ]


def test_local_stack_acceptance_uses_the_freecm_service_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        acceptance,
        "_running_services",
        lambda _environment: frozenset(workflow.INFRASTRUCTURE_SERVICES),
    )
    acceptance._assert_interruption_boundary({"TEST": "1"})

    monkeypatch.setattr(
        acceptance,
        "_running_services",
        lambda _environment: frozenset(
            (*workflow.INFRASTRUCTURE_SERVICES, workflow.APPLICATION_SERVICES[0])
        ),
    )
    with pytest.raises(acceptance.AcceptanceError, match="left application services running"):
        acceptance._assert_interruption_boundary({"TEST": "1"})


def test_local_stack_acceptance_requires_sigint_exit_130() -> None:
    class FakeProcess:
        sent_signals: list[int]

        def __init__(self, *, return_code: int) -> None:
            self.return_code = return_code
            self.sent_signals = []

        def poll(self) -> None:
            return None

        def send_signal(self, signal_number: int) -> None:
            self.sent_signals.append(signal_number)

        def wait(self, timeout: float | None = None) -> int:
            assert timeout == 20
            return self.return_code

    accepted = FakeProcess(return_code=130)
    acceptance._interrupt_run(cast("subprocess.Popen[bytes]", accepted))
    assert accepted.sent_signals == [signal.SIGINT]

    rejected = FakeProcess(return_code=0)
    with pytest.raises(acceptance.AcceptanceError, match="instead of 130"):
        acceptance._interrupt_run(cast("subprocess.Popen[bytes]", rejected))


def test_ci_invokes_python_local_stack_acceptance() -> None:
    workflow_text = (workflow.REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python3 -m configs.test_local_stack_acceptance" in workflow_text
    assert "timeout-minutes: 60" in workflow_text
    assert not (workflow.REPO_ROOT / "deploy/scripts/test-local-stack-acceptance.sh").exists()


def test_real_service_ci_jobs_reclaim_hosted_runner_disk() -> None:
    workflow_text = (workflow.REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    integration_job = workflow_text.split("\n  m1-integration:\n", 1)[1].split(
        "\n  migrations:\n", 1
    )[0]
    acceptance_job = workflow_text.split("\n  local-stack-acceptance:\n", 1)[1]

    for job in (integration_job, acceptance_job):
        assert job.count("Reclaim runner disk for real-service tests") == 1
        assert job.count("/opt/hostedtoolcache/CodeQL") == 1
        assert job.count("/usr/local/lib/android") == 1
        assert job.count("docker system prune --all --force --volumes") == 1
        assert job.index("Reclaim runner disk for real-service tests") < job.index(
            "actions/setup-python@v6"
        )


def test_ci_runtime_contract_receipts_forbid_skips() -> None:
    workflow_text = (workflow.REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    integration_job = workflow_text.split("\n  m1-integration:\n", 1)[1].split(
        "\n  migrations:\n", 1
    )[0]
    runtime_contract_test = (
        workflow.REPO_ROOT / "tests/test_database_contract_postgres.py"
    ).read_text(encoding="utf-8")

    for role in ("app", "worker", "verifier"):
        assert f'--junitxml="$RUNNER_TEMP/runtime-contract-{role}.xml"' in integration_job
    assert "Assert runtime contract tests did not skip" in integration_job
    assert "if not cases or skipped:" in integration_job
    assert "pytest.mark.skip" not in runtime_contract_test
    assert "skipping is forbidden" in runtime_contract_test


def test_package_platform_comes_from_built_images() -> None:
    metadata = [
        {"Os": "linux", "Architecture": "arm64"},
        {"Os": "linux", "Architecture": "arm64"},
    ]

    assert workflow._image_platform(metadata) == "linux-arm64"

    with pytest.raises(workflow.WorkflowError, match="do not share"):
        workflow._image_platform([*metadata, {"Os": "linux", "Architecture": "amd64"}])


def test_run_never_builds_and_stops_only_application_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checked: list[tuple[str, ...]] = []
    unchecked: list[tuple[str, ...]] = []

    monkeypatch.setattr(workflow, "require_configuration", lambda: None)
    monkeypatch.setattr(workflow, "require_docker", lambda _environment: None)
    monkeypatch.setattr(workflow, "workflow_environment", lambda: {"TEST": "1"})
    monkeypatch.setattr(workflow, "require_runtime_prepared", lambda _environment: None)
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
    assert checked == [
        (
            "docker",
            "compose",
            "up",
            "--detach",
            "--wait",
            "--wait-timeout",
            "60",
            "--no-build",
            "--no-deps",
            *workflow.APPLICATION_SERVICES,
        )
    ]
    assert unchecked[0] == (
        "docker",
        "compose",
        "logs",
        "--follow",
        "--since",
        "10s",
        *workflow.APPLICATION_SERVICES,
    )
    assert unchecked[-1] == (
        "docker",
        "compose",
        "stop",
        *reversed(workflow.APPLICATION_SERVICES),
    )


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
