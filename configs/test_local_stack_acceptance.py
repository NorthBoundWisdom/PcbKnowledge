#!/usr/bin/env python3
"""Qualify the prepared local identity, verifier, browser intake, and Run contract."""

from __future__ import annotations

import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from configs.pcbknowledge_workflow import (
    APPLICATION_SERVICES,
    FREECM_ENVIRONMENT,
    INFRASTRUCTURE_SERVICES,
    REPO_ROOT,
    workflow_environment,
)


class AcceptanceError(RuntimeError):
    """The executable local-stack contract did not hold."""


def _run_checked(command: Sequence[str], environment: Mapping[str, str]) -> None:
    print(f"[pcbknowledge-acceptance] {' '.join(command)}", flush=True)
    subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        env=dict(environment),
        check=True,
    )


def _wait_until_ready(process: subprocess.Popen[bytes], *, port: str) -> None:
    endpoint = f"http://localhost:{port}/api/v1/readyz"
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise AcceptanceError(
                f"FreeCM Run exited with {return_code} before the application became ready"
            )
        try:
            with urlopen(endpoint, timeout=2) as response:
                if response.status == 200:
                    return
        except HTTPError, URLError, TimeoutError:
            pass
        time.sleep(1)
    raise AcceptanceError("FreeCM Run did not become ready within 60 seconds")


def _interrupt_run(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        raise AcceptanceError("FreeCM Run exited before browser acceptance completed")
    process.send_signal(signal.SIGINT)
    try:
        return_code = process.wait(timeout=20)
    except subprocess.TimeoutExpired as error:
        raise AcceptanceError("FreeCM Run did not honor SIGINT within 20 seconds") from error
    if return_code != 130:
        raise AcceptanceError(f"FreeCM Run returned {return_code} after SIGINT instead of 130")


def _running_services(environment: Mapping[str, str]) -> frozenset[str]:
    result = subprocess.run(
        ["docker", "compose", "ps", "--status", "running", "--services"],
        cwd=REPO_ROOT,
        env=dict(environment),
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return frozenset(result.stdout.splitlines())


def _assert_interruption_boundary(environment: Mapping[str, str]) -> None:
    running = _running_services(environment)
    unexpected = sorted(set(APPLICATION_SERVICES) & running)
    missing = sorted(set(INFRASTRUCTURE_SERVICES) - running)
    if unexpected:
        raise AcceptanceError(
            f"FreeCM Run interruption left application services running: {unexpected}"
        )
    if missing:
        raise AcceptanceError(
            f"FreeCM Run interruption did not preserve infrastructure services: {missing}"
        )


def _cleanup_failed_run(
    process: subprocess.Popen[bytes] | None,
    environment: Mapping[str, str],
) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    subprocess.run(
        ["docker", "compose", "stop", *reversed(APPLICATION_SERVICES)],
        cwd=REPO_ROOT,
        env=dict(environment),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_acceptance() -> None:
    if shutil.which("pnpm") is None:
        raise AcceptanceError("pnpm is required for the live browser acceptance test")

    environment = workflow_environment()
    _run_checked(["/bin/sh", "deploy/scripts/test-local-development-bootstrap.sh"], environment)
    _run_checked(["/bin/sh", "deploy/scripts/test-verifier-runtime-boundary.sh"], environment)

    process: subprocess.Popen[bytes] | None = None
    completed = False
    with tempfile.TemporaryDirectory(prefix="pcbknowledge-acceptance-") as temporary:
        log_path = Path(temporary) / "freecm-run.log"
        try:
            with log_path.open("wb") as log:
                process = subprocess.Popen(
                    [sys.executable, "configs/pcbknowledge_workflow.py", "run"],
                    cwd=REPO_ROOT,
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                _wait_until_ready(
                    process,
                    port=FREECM_ENVIRONMENT["PCBKNOWLEDGE_HTTP_PORT"],
                )
                browser_environment = dict(environment)
                browser_environment.update(
                    {
                        "PCBKNOWLEDGE_E2E_LIVE_BASE_URL": (
                            f"http://localhost:{FREECM_ENVIRONMENT['PCBKNOWLEDGE_HTTP_PORT']}"
                        ),
                        "PCBKNOWLEDGE_E2E_PASSWORD_FILE": str(
                            REPO_ROOT / "deploy/secrets/local_curator_password"
                        ),
                    }
                )
                _run_checked(
                    [
                        "pnpm",
                        "--dir",
                        "apps/curator-web",
                        "exec",
                        "playwright",
                        "test",
                    ],
                    browser_environment,
                )
                _interrupt_run(process)
            _assert_interruption_boundary(environment)
            completed = True
        finally:
            if not completed:
                _cleanup_failed_run(process, environment)


def main() -> int:
    try:
        run_acceptance()
    except AcceptanceError as error:
        print(f"[pcbknowledge-acceptance] {error}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        return error.returncode if error.returncode > 0 else 1
    except KeyboardInterrupt:
        return 130
    print(
        "[pcbknowledge-acceptance] local identity, verifier boundary, live browser "
        "intake, and lightweight Run passed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
