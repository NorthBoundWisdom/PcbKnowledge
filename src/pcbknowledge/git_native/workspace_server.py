"""Workspace-aware wrapper around the stable loopback Source Corpus server."""

from __future__ import annotations

import html
import secrets
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path

from pcbknowledge.git_native.server import (
    DEFAULT_PORT,
    EditorHTTPServer,
    EditorRequestHandler,
)
from pcbknowledge.git_native.store import KnowledgeRepository
from pcbknowledge.git_native.workspace import validate_workspace


class WorkspaceEditorRequestHandler(EditorRequestHandler):
    """Add explicit workspace identity without changing the Source editor contract."""

    def _send_html(self, payload: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        label = html.escape(str(self.repository.root), quote=True)
        banner = (
            '<section class="notice workspace-notice">'
            '<strong>Selected knowledge workspace</strong>'
            f'<p><code>{label}</code></p>'
            '</section>'
        )
        if "<main>" in payload:
            payload = payload.replace("<main>", "<main>" + banner, 1)
        super()._send_html(payload, status)


class WorkspaceEditorHTTPServer(EditorHTTPServer):
    def __init__(self, address: tuple[str, int], repository: KnowledgeRepository) -> None:
        ThreadingHTTPServer.__init__(self, address, WorkspaceEditorRequestHandler)
        self.repository = repository
        self.csrf_token = secrets.token_urlsafe(32)


def create_server(
    repository_root: Path, port: int = DEFAULT_PORT
) -> WorkspaceEditorHTTPServer:
    validation = validate_workspace(repository_root)
    repository = KnowledgeRepository(validation.root)
    repository.ensure_layout()
    repository.validate_all(require_canonical=True)
    return WorkspaceEditorHTTPServer(("127.0.0.1", port), repository)
