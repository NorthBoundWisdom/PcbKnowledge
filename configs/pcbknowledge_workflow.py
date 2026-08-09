#!/usr/bin/env python3
# Usage:
#   python3 configs/pcbknowledge_workflow.py config
#   python3 configs/pcbknowledge_workflow.py build
#   python3 configs/pcbknowledge_workflow.py run
#   python3 configs/pcbknowledge_workflow.py test
#   python3 configs/pcbknowledge_workflow.py package

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIGURATION_ID = "freecm-compose"
CONFIG_RECEIPT = Path(".freecm/pcbknowledge-compose.json")
RUNTIME_RECEIPT = Path(".freecm/pcbknowledge-runtime.json")
CONFIG_INPUTS = (
    Path(".dockerignore"),
    Path("configs/freecm.commands.jsonc"),
    Path("configs/pcbknowledge_workflow.py"),
    Path("compose.yaml"),
    Path("deploy/caddy/Caddyfile"),
    Path("deploy/docker/backend-entrypoint.sh"),
    Path("deploy/docker/backend.Dockerfile"),
    Path("deploy/docker/web.Dockerfile"),
    Path("deploy/keycloak/pcbknowledge-agent-client.template.json"),
    Path("deploy/keycloak/pcbknowledge-api-client.json"),
    Path("deploy/keycloak/pcbknowledge-curator-client.json"),
    Path("deploy/keycloak/pcbknowledge-realm.template.json"),
    Path("deploy/keycloak/bootstrap-local-curator.sh"),
    Path("deploy/keycloak/reconcile-keycloak.sh"),
    Path("deploy/keycloak/run-as-keycloak.sh"),
    Path("deploy/keycloak/start-keycloak.sh"),
    Path("deploy/observability/grafana/dashboards/m1-platform.json"),
    Path("deploy/observability/grafana/provisioning/dashboards/pcbknowledge.yaml"),
    Path("deploy/observability/grafana/provisioning/datasources/prometheus.yaml"),
    Path("deploy/observability/grafana/start-grafana.sh"),
    Path("deploy/observability/otel-collector.yaml"),
    Path("deploy/observability/prometheus.yml"),
    Path("deploy/observability/rules/platform.yml"),
    Path("deploy/postgres/bootstrap-local-development-data.sh"),
    Path("deploy/postgres/init/001-keycloak-database.sh"),
    Path("deploy/postgres/reconcile-application-role.sh"),
    Path("deploy/postgres/start-postgres.sh"),
    Path("deploy/seaweedfs/start-seaweedfs.sh"),
    Path("deploy/scripts/bootstrap-secrets.sh"),
    Path("deploy/scripts/bootstrap-local-development.sh"),
    Path("deploy/scripts/compose-check.sh"),
    Path("deploy/scripts/test-backend-hermetic.sh"),
    Path("deploy/scripts/test-frontend-hermetic.sh"),
    Path("deploy/scripts/test-verifier-deployment-wiring.sh"),
    Path("package.json"),
    Path("pnpm-lock.yaml"),
    Path("pnpm-workspace.yaml"),
    Path("pyproject.toml"),
    Path("uv.lock"),
)
CONFIG_SECRET_OUTPUTS = (
    Path("deploy/secrets/postgres_password"),
    Path("deploy/secrets/application_db_password"),
    Path("deploy/secrets/worker_db_password"),
    Path("deploy/secrets/verifier_db_password"),
    Path("deploy/secrets/keycloak_db_password"),
    Path("deploy/secrets/keycloak_admin_password"),
    Path("deploy/secrets/agent_service_client_secret"),
    Path("deploy/secrets/local_curator_password"),
    Path("deploy/secrets/local_curator_marker"),
    Path("deploy/secrets/seaweedfs_access_key"),
    Path("deploy/secrets/seaweedfs_secret_key"),
    Path("deploy/secrets/seaweedfs_admin_access_key"),
    Path("deploy/secrets/seaweedfs_admin_secret_key"),
    Path("deploy/secrets/seaweedfs_worker_access_key"),
    Path("deploy/secrets/seaweedfs_worker_secret_key"),
    Path("deploy/secrets/seaweedfs_verifier_access_key"),
    Path("deploy/secrets/seaweedfs_verifier_secret_key"),
    Path("deploy/secrets/grafana_admin_password"),
    Path("deploy/secrets/keycloak-realm.json"),
    Path("deploy/secrets/keycloak-agent-client.json"),
)
BUILD_INPUT_FILES = (
    Path("README.md"),
    Path("deploy/docker/nginx.conf"),
    Path("package.json"),
    Path("pnpm-lock.yaml"),
    Path("pnpm-workspace.yaml"),
    Path("pyproject.toml"),
    Path("uv.lock"),
)
BUILD_INPUT_ROOTS = (
    Path("apps/api"),
    Path("apps/curator-web"),
    Path("apps/worker"),
    Path("migrations"),
    Path("packages/ui-kit"),
    Path("src"),
)
_IGNORED_BUILD_INPUT_PARTS = frozenset(
    {
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".vite",
        "__pycache__",
        "coverage",
        "dist",
        "node_modules",
        "playwright-report",
        "test-results",
    }
)
FREECM_ENVIRONMENT = {
    "COMPOSE_PROJECT_NAME": "pcbknowledge-freecm",
    "PCBKNOWLEDGE_HTTP_PORT": "18080",
    "PCBKNOWLEDGE_KEYCLOAK_PORT": "18081",
    "PCBKNOWLEDGE_S3_PORT": "18333",
    "PCBKNOWLEDGE_PROMETHEUS_PORT": "19090",
    "PCBKNOWLEDGE_GRAFANA_PORT": "13000",
}
BUILD_SERVICES = ("api", "worker", "verifier", "web", "migrate", "storage-init")
TEST_SERVICES = ("backend-test", "frontend-test")
APPLICATION_SERVICES = (
    "api",
    "worker",
    "verifier",
    "web",
    "caddy",
)
INFRASTRUCTURE_SERVICES = (
    "keycloak",
    "postgres",
    "seaweedfs",
    "otel-collector",
    "prometheus",
    "grafana",
)
_BACKEND_RUNTIME_BOUNDARY_CHECK = r"""
entrypoint=/usr/local/bin/pcbknowledge-backend-entrypoint
test "$(stat -c '%u:%g:%a' "$entrypoint")" = 0:0:555
test "$(stat -c '%u:%g' /usr/local/bin)" = 0:0

replacement=/tmp/pcbknowledge-entrypoint-replacement
printf 'replacement\n' >"$replacement"
chown pcbknowledge:pcbknowledge "$replacement"
if /usr/bin/setpriv --reuid=pcbknowledge --regid=pcbknowledge --init-groups -- \
  /bin/mv "$replacement" "$entrypoint" 2>/dev/null; then
  echo "backend runtime account replaced the privileged entrypoint" >&2
  exit 1
fi

/usr/bin/setpriv --reuid=pcbknowledge --regid=pcbknowledge --init-groups -- \
  /bin/sh -ec '
    printf "#!/bin/sh\n" > /workspace/.venv/bin/tr
    printf "/usr/bin/touch /tmp/untrusted-runtime-tool-executed\n" >> /workspace/.venv/bin/tr
    printf "exec /usr/bin/tr \"\$@\"\n" >> /workspace/.venv/bin/tr
    printf "#!/bin/sh\n" > /workspace/.venv/bin/id
    printf "/usr/bin/touch /tmp/untrusted-runtime-tool-executed\n" >> /workspace/.venv/bin/id
    printf "exec /usr/bin/id \"\$@\"\n" >> /workspace/.venv/bin/id
    chmod 755 /workspace/.venv/bin/tr /workspace/.venv/bin/id
  '

secret_directory=/tmp/pcbknowledge-runtime-boundary-secrets
mkdir -p "$secret_directory"
printf 'database-password\n' >"$secret_directory/application_db_password"
printf 's3-access-key\n' >"$secret_directory/seaweedfs_access_key"
printf 's3-secret-key\n' >"$secret_directory/seaweedfs_secret_key"
chmod 600 "$secret_directory"/*

PCBKNOWLEDGE_SECRET_DIRECTORY=$secret_directory \
PCBKNOWLEDGE_DATABASE_USERNAME=pcbknowledge_app \
  /bin/sh "$entrypoint" /bin/sh -ec '
    test "$(/usr/bin/id -u)" -eq 999
    test ! -e /tmp/untrusted-runtime-tool-executed
  '
""".strip()


class WorkflowError(RuntimeError):
    """A deterministic repository workflow contract failure."""


def workflow_environment(base: Mapping[str, str] | None = None) -> dict[str, str]:
    environment = dict(os.environ if base is None else base)
    environment.update(FREECM_ENVIRONMENT)
    return environment


def _display_command(command: Sequence[str]) -> None:
    print(f"[pcbknowledge] {shlex.join(command)}", flush=True)


def _run_checked(command: Sequence[str], *, environment: Mapping[str, str]) -> None:
    _display_command(command)
    subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        env=dict(environment),
        check=True,
    )


def _run_unchecked(command: Sequence[str], *, environment: Mapping[str, str]) -> int:
    _display_command(command)
    result = subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        env=dict(environment),
        check=False,
    )
    return result.returncode


def _capture(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    display: bool = True,
) -> str:
    if display:
        _display_command(command)
    result = subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        env=dict(environment),
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def configuration_signature(repo_root: Path = REPO_ROOT) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(FREECM_ENVIRONMENT, sort_keys=True).encode())
    for relative_path in CONFIG_INPUTS:
        path = repo_root / relative_path
        if not path.is_file():
            raise WorkflowError(f"configuration input is missing: {relative_path}")
        digest.update(str(relative_path).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_input_signature(repo_root: Path = REPO_ROOT) -> str:
    """Hash every source file copied into a repository-owned runtime image."""

    digest = hashlib.sha256()
    candidates: list[Path] = []
    for relative_path in BUILD_INPUT_FILES:
        path = repo_root / relative_path
        if not path.is_file() or path.is_symlink():
            raise WorkflowError(f"application build input is missing or unsafe: {relative_path}")
        candidates.append(path)
    for relative_root in BUILD_INPUT_ROOTS:
        root = repo_root / relative_root
        if not root.is_dir() or root.is_symlink():
            raise WorkflowError(
                f"application build input root is missing or unsafe: {relative_root}"
            )
        for path in root.rglob("*"):
            relative_path = path.relative_to(repo_root)
            if any(part in _IGNORED_BUILD_INPUT_PARTS for part in relative_path.parts):
                continue
            if (
                path.suffix in {".log", ".pid", ".pyc", ".pyo", ".tmp"}
                or path.name == ".DS_Store"
                or path.name.endswith(".tsbuildinfo")
            ):
                continue
            if path.is_symlink():
                raise WorkflowError(
                    f"application build input is an unsafe symlink: {relative_path}"
                )
            if path.is_file():
                candidates.append(path)
    for path in sorted(
        candidates, key=lambda candidate: candidate.relative_to(repo_root).as_posix()
    ):
        relative_path = path.relative_to(repo_root)
        digest.update(relative_path.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _receipt_path(repo_root: Path) -> Path:
    return repo_root / CONFIG_RECEIPT


def write_configuration_receipt(repo_root: Path = REPO_ROOT) -> Path:
    receipt_path = _receipt_path(repo_root)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schemaVersion": 1,
        "configurationId": CONFIGURATION_ID,
        "signature": configuration_signature(repo_root),
        "composeProject": FREECM_ENVIRONMENT["COMPOSE_PROJECT_NAME"],
        "endpoints": {
            "curator": "http://localhost:18080",
            "keycloak": "http://localhost:18081",
            "s3": "http://localhost:18333",
            "prometheus": "http://localhost:19090",
            "grafana": "http://localhost:13000",
        },
        "configuredAt": datetime.now(UTC).isoformat(),
    }
    temporary = receipt_path.with_name(f"{receipt_path.name}.tmp")
    temporary.write_text(f"{json.dumps(receipt, indent=2, sort_keys=True)}\n", encoding="utf-8")
    os.replace(temporary, receipt_path)
    return receipt_path


def require_configuration(repo_root: Path = REPO_ROOT) -> None:
    receipt_path = _receipt_path(repo_root)
    try:
        receipt: Any = json.loads(receipt_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise WorkflowError(
            "FreeCM configuration is missing; run "
            "`python3 configs/pcbknowledge_workflow.py config` first"
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        raise WorkflowError(f"FreeCM configuration receipt is invalid: {error}") from error

    if not isinstance(receipt, dict) or receipt.get("configurationId") != CONFIGURATION_ID:
        raise WorkflowError("FreeCM configuration receipt has the wrong configuration ID")
    if receipt.get("signature") != configuration_signature(repo_root):
        raise WorkflowError(
            "FreeCM configuration inputs changed; rerun "
            "`python3 configs/pcbknowledge_workflow.py config`"
        )
    for relative_path in CONFIG_SECRET_OUTPUTS:
        path = repo_root / relative_path
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            raise WorkflowError(
                f"FreeCM configuration output is missing or invalid: {relative_path}; "
                "rerun `python3 configs/pcbknowledge_workflow.py config`"
            )
        if path.stat().st_mode & 0o077:
            raise WorkflowError(
                f"FreeCM configuration output is not owner-only: {relative_path}; "
                "rerun `python3 configs/pcbknowledge_workflow.py config`"
            )


def require_docker(environment: Mapping[str, str]) -> None:
    if shutil.which("docker") is None:
        raise WorkflowError("docker is required for the PcbKnowledge FreeCM workflow")
    _run_checked(["docker", "compose", "version"], environment=environment)


def cmd_config() -> int:
    environment = workflow_environment()
    require_docker(environment)
    _run_checked(
        ["/bin/sh", "deploy/scripts/compose-check.sh"],
        environment=environment,
    )
    receipt_path = write_configuration_receipt()
    print(f"[pcbknowledge] configuration receipt: {receipt_path.relative_to(REPO_ROOT)}")
    print("[pcbknowledge] curator: http://localhost:18080")
    return 0


def _build_images(environment: Mapping[str, str]) -> None:
    _run_checked(
        ["docker", "compose", "--profile", "tools", "build", *BUILD_SERVICES],
        environment=environment,
    )
    _run_checked(
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "/bin/sh",
            package_image_names()[0],
            "-ec",
            _BACKEND_RUNTIME_BOUNDARY_CHECK,
        ],
        environment=environment,
    )


def _runtime_image_ids(environment: Mapping[str, str]) -> dict[str, str]:
    image_ids: dict[str, str] = {}
    for service, image_name in zip(BUILD_SERVICES, package_image_names(), strict=True):
        try:
            image_id = _capture(
                ["docker", "image", "inspect", "--format", "{{.Id}}", image_name],
                environment=environment,
                display=False,
            )
        except subprocess.CalledProcessError as error:
            raise WorkflowError(
                f"prepared image is missing for {service}; run FreeCM Build"
            ) from error
        if not image_id:
            raise WorkflowError(f"prepared image is missing for {service}; run FreeCM Build")
        image_ids[service] = image_id
    return image_ids


def write_runtime_receipt(
    environment: Mapping[str, str],
    repo_root: Path = REPO_ROOT,
) -> Path:
    receipt_path = repo_root / RUNTIME_RECEIPT
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schemaVersion": 2,
        "configurationId": CONFIGURATION_ID,
        "configurationSignature": configuration_signature(repo_root),
        "buildInputSignature": build_input_signature(repo_root),
        "composeProject": FREECM_ENVIRONMENT["COMPOSE_PROJECT_NAME"],
        "images": _runtime_image_ids(environment),
        "preparedAt": datetime.now(UTC).isoformat(),
    }
    temporary = receipt_path.with_name(f"{receipt_path.name}.tmp")
    temporary.write_text(f"{json.dumps(receipt, indent=2, sort_keys=True)}\n", encoding="utf-8")
    os.replace(temporary, receipt_path)
    return receipt_path


def _require_infrastructure_ready(environment: Mapping[str, str]) -> None:
    failures: list[str] = []
    for service in INFRASTRUCTURE_SERVICES:
        container_id = _capture(
            ["docker", "compose", "ps", "--all", "--quiet", service],
            environment=environment,
            display=False,
        )
        if not container_id:
            failures.append(f"{service}=missing")
            continue
        try:
            state_value: Any = json.loads(
                _capture(
                    ["docker", "inspect", "--format", "{{json .State}}", container_id],
                    environment=environment,
                    display=False,
                )
            )
        except json.JSONDecodeError:
            failures.append(f"{service}=unavailable")
            continue
        except subprocess.CalledProcessError:
            failures.append(f"{service}=unavailable")
            continue
        if not isinstance(state_value, dict) or state_value.get("Status") != "running":
            failures.append(f"{service}=not-running")
            continue
        health_value = state_value.get("Health")
        if isinstance(health_value, dict) and health_value.get("Status") != "healthy":
            failures.append(f"{service}=not-healthy")
    if failures:
        raise WorkflowError(
            f"prepared runtime is not ready ({', '.join(failures)}); run FreeCM Build before Run"
        )


def require_runtime_prepared(
    environment: Mapping[str, str],
    repo_root: Path = REPO_ROOT,
) -> None:
    receipt_path = repo_root / RUNTIME_RECEIPT
    try:
        receipt: Any = json.loads(receipt_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise WorkflowError("prepared runtime is missing; run FreeCM Build before Run") from error
    except (OSError, json.JSONDecodeError) as error:
        raise WorkflowError(f"prepared runtime receipt is invalid: {error}") from error

    if not isinstance(receipt, dict) or receipt.get("configurationId") != CONFIGURATION_ID:
        raise WorkflowError("prepared runtime receipt is invalid; rerun FreeCM Build")
    if receipt.get("configurationSignature") != configuration_signature(repo_root):
        raise WorkflowError("runtime inputs changed; rerun FreeCM Config and Build")
    if receipt.get("buildInputSignature") != build_input_signature(repo_root):
        raise WorkflowError("application build inputs changed; rerun FreeCM Build")
    if receipt.get("composeProject") != FREECM_ENVIRONMENT["COMPOSE_PROJECT_NAME"]:
        raise WorkflowError("prepared runtime belongs to another Compose project")
    if receipt.get("images") != _runtime_image_ids(environment):
        raise WorkflowError("prepared runtime images changed; rerun FreeCM Build")
    _require_infrastructure_ready(environment)


def _prepare_runtime(environment: Mapping[str, str]) -> None:
    _run_checked(
        ["docker", "compose", "stop", *APPLICATION_SERVICES],
        environment=environment,
    )
    _build_images(environment)
    _run_checked(
        [
            "docker",
            "compose",
            "up",
            "--detach",
            "--wait",
            "--force-recreate",
            "postgres",
        ],
        environment=environment,
    )
    _run_checked(
        [
            "docker",
            "compose",
            "up",
            "--detach",
            "--wait",
            "--force-recreate",
            "seaweedfs",
        ],
        environment=environment,
    )
    _run_checked(
        [
            "docker",
            "compose",
            "up",
            "--detach",
            "--wait",
            "--force-recreate",
            "keycloak",
        ],
        environment=environment,
    )
    _run_checked(
        ["docker", "compose", "run", "--rm", "keycloak-reconcile"],
        environment=environment,
    )
    _run_checked(
        [
            "docker",
            "compose",
            "up",
            "--detach",
            "--force-recreate",
            "otel-collector",
            "prometheus",
            "grafana",
        ],
        environment=environment,
    )
    for service in ("migrate", "postgres-reconcile"):
        _run_checked(
            ["docker", "compose", "run", "--rm", service],
            environment=environment,
        )
    _run_checked(
        ["/bin/sh", "deploy/scripts/bootstrap-local-development.sh"],
        environment=environment,
    )
    _run_checked(
        ["docker", "compose", "run", "--rm", "storage-init"],
        environment=environment,
    )
    _run_checked(
        [
            "docker",
            "compose",
            "up",
            "--no-start",
            "--no-build",
            "--no-deps",
            *APPLICATION_SERVICES,
        ],
        environment=environment,
    )


def cmd_build() -> int:
    require_configuration()
    environment = workflow_environment()
    require_docker(environment)
    _prepare_runtime(environment)
    receipt_path = write_runtime_receipt(environment)
    print(f"[pcbknowledge] prepared runtime receipt: {receipt_path.relative_to(REPO_ROOT)}")
    print("[pcbknowledge] infrastructure is warm; FreeCM Run now starts only application services")
    return 0


def cmd_test() -> int:
    require_configuration()
    environment = workflow_environment()
    require_docker(environment)
    _run_checked(
        ["/bin/sh", "deploy/scripts/test-verifier-deployment-wiring.sh"],
        environment=environment,
    )
    _run_checked(
        ["docker", "compose", "--profile", "tools", "build", *TEST_SERVICES],
        environment=environment,
    )
    for service in TEST_SERVICES:
        _run_checked(
            [
                "docker",
                "compose",
                "--profile",
                "tools",
                "run",
                "--rm",
                "--no-deps",
                service,
            ],
            environment=environment,
        )
    return 0


def cmd_run() -> int:
    require_configuration()
    environment = workflow_environment()
    require_docker(environment)
    require_runtime_prepared(environment)
    exit_code = 1
    try:
        _run_checked(
            [
                "docker",
                "compose",
                "up",
                "--detach",
                "--wait",
                "--wait-timeout",
                "60",
                "--no-build",
                "--no-deps",
                *APPLICATION_SERVICES,
            ],
            environment=environment,
        )
        print(
            "[pcbknowledge] applications ready at http://localhost:18080; "
            "Ctrl+C stops applications and leaves infrastructure warm"
        )
        exit_code = _run_unchecked(
            [
                "docker",
                "compose",
                "logs",
                "--follow",
                "--since",
                "10s",
                *APPLICATION_SERVICES,
            ],
            environment=environment,
        )
    except KeyboardInterrupt:
        exit_code = 130
    finally:
        print("[pcbknowledge] stopping application services; infrastructure stays warm", flush=True)
        stop_code = _run_unchecked(
            ["docker", "compose", "stop", *reversed(APPLICATION_SERVICES)],
            environment=environment,
        )
        if exit_code == 0 and stop_code != 0:
            exit_code = stop_code
    return exit_code


def package_image_names() -> tuple[str, ...]:
    project = FREECM_ENVIRONMENT["COMPOSE_PROJECT_NAME"]
    return tuple(f"{project}-{service}:latest" for service in BUILD_SERVICES)


def _working_tree_identity(environment: Mapping[str, str]) -> tuple[str, bool]:
    revision = _capture(
        ["git", "rev-parse", "--short=12", "HEAD"],
        environment=environment,
    )
    dirty = bool(_capture(["git", "status", "--porcelain"], environment=environment))
    return revision, dirty


def _create_image_archive(
    images: Sequence[str],
    output_path: Path,
    *,
    environment: Mapping[str, str],
) -> None:
    temporary = output_path.with_name(f"{output_path.name}.tmp")
    command = ["docker", "image", "save", *images]
    _display_command(command)
    process = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        env=dict(environment),
        stdout=subprocess.PIPE,
    )
    if process.stdout is None:
        process.kill()
        raise WorkflowError("docker image save did not provide an output stream")
    try:
        with (
            temporary.open("wb") as stream,
            gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed,
        ):
            shutil.copyfileobj(process.stdout, compressed)
        process.stdout.close()
        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)
        os.replace(temporary, output_path)
    except BaseException:
        process.stdout.close()
        if process.poll() is None:
            process.terminate()
            process.wait()
        temporary.unlink(missing_ok=True)
        raise


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_package_manifest(
    path: Path,
    *,
    revision: str,
    dirty: bool,
    archive: Path,
    archive_sha256: str,
    image_metadata: Sequence[Mapping[str, Any]],
) -> None:
    images = [
        {
            "id": metadata.get("Id"),
            "repoTags": metadata.get("RepoTags", []),
            "os": metadata.get("Os"),
            "architecture": metadata.get("Architecture"),
        }
        for metadata in image_metadata
    ]
    manifest = {
        "schemaVersion": 1,
        "archiveFormat": "docker-image-archive+gzip",
        "sourceRevision": revision,
        "sourceDirty": dirty,
        "archive": archive.name,
        "archiveSha256": archive_sha256,
        "images": images,
        "createdAt": datetime.now(UTC).isoformat(),
    }
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(f"{json.dumps(manifest, indent=2, sort_keys=True)}\n", encoding="utf-8")
    os.replace(temporary, path)


def _image_platform(image_metadata: Sequence[Mapping[str, Any]]) -> str:
    platforms = {(metadata.get("Os"), metadata.get("Architecture")) for metadata in image_metadata}
    if len(platforms) != 1:
        raise WorkflowError("package images do not share one operating system and architecture")
    image_os, image_architecture = platforms.pop()
    if not isinstance(image_os, str) or not image_os:
        raise WorkflowError("package image operating system metadata is missing")
    if not isinstance(image_architecture, str) or not image_architecture:
        raise WorkflowError("package image architecture metadata is missing")
    return f"{image_os.lower()}-{image_architecture.lower()}"


def cmd_package() -> int:
    require_configuration()
    environment = workflow_environment()
    require_docker(environment)
    require_runtime_prepared(environment)

    image_names = package_image_names()
    metadata_value: Any = json.loads(
        _capture(["docker", "image", "inspect", *image_names], environment=environment)
    )
    if not isinstance(metadata_value, list) or len(metadata_value) != len(image_names):
        raise WorkflowError("docker returned incomplete image metadata for the package")

    revision, dirty = _working_tree_identity(environment)
    platform_slug = _image_platform(metadata_value)
    source_slug = f"{revision}-dirty" if dirty else revision
    package_dir = REPO_ROOT / "build" / "package"
    package_dir.mkdir(parents=True, exist_ok=True)
    archive = package_dir / f"PcbKnowledge_{source_slug}_{platform_slug}_docker-images.tar.gz"
    _create_image_archive(image_names, archive, environment=environment)
    archive_sha256 = _sha256(archive)

    checksum = archive.with_suffix(f"{archive.suffix}.sha256")
    checksum.write_text(f"{archive_sha256}  {archive.name}\n", encoding="utf-8")
    manifest = archive.with_suffix(f"{archive.suffix}.manifest.json")
    _write_package_manifest(
        manifest,
        revision=revision,
        dirty=dirty,
        archive=archive,
        archive_sha256=archive_sha256,
        image_metadata=metadata_value,
    )
    print(f"[pcbknowledge] package archive: {archive.relative_to(REPO_ROOT)}")
    print(f"[pcbknowledge] package sha256: {archive_sha256}")
    return 0


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PcbKnowledge FreeCM repository workflow.")
    parser.add_argument("action", choices=("config", "build", "run", "test", "package"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.action == "config":
            return cmd_config()
        if args.action == "build":
            return cmd_build()
        if args.action == "run":
            return cmd_run()
        if args.action == "test":
            return cmd_test()
        return cmd_package()
    except WorkflowError as error:
        print(f"[pcbknowledge] {error}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        return error.returncode if error.returncode > 0 else 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
