"""Workspace validation boundary for the typed loopback workbench."""

from __future__ import annotations

from pathlib import Path

from pcbknowledge.git_native.server import (
    DEFAULT_PORT,
    EditorHTTPServer,
    create_server as create_editor_server,
)
from pcbknowledge.git_native.workspace import validate_workspace


def create_server(
    repository_root: Path, port: int = DEFAULT_PORT
) -> EditorHTTPServer:
    """Validate the selected workspace before constructing the editor server."""

    validation = validate_workspace(repository_root)
    return create_editor_server(validation.root, port)
