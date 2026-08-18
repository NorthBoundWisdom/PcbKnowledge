"""Workspace-aware loopback server with typed visual evidence review."""

from __future__ import annotations

import html
import secrets
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from pcbknowledge.git_native.evidence_review import EvidenceReviewApplication
from pcbknowledge.git_native.evidence_review_views import render_fact_evidence_review
from pcbknowledge.git_native.pdfjs_vendor import PdfJsVendorError, validate_pdfjs_vendor
from pcbknowledge.git_native.server import (
    DEFAULT_PORT,
    EditorHTTPServer,
    EditorRequestHandler,
    HTTPRequestError,
)
from pcbknowledge.git_native.store import KnowledgeRepository, RepositoryError
from pcbknowledge.git_native.workbench import WorkbenchApplication
from pcbknowledge.git_native.workspace import validate_workspace


_STATIC_ROOT = Path(__file__).with_name("static")
_PDFJS_ROOT = _STATIC_ROOT / "vendor" / "pdfjs" / "6.2.108"
_STATIC_ASSETS: dict[str, tuple[Path, str, str]] = {
    "/static/evidence-review.css": (
        _STATIC_ROOT / "evidence-review.css",
        "text/css; charset=utf-8",
        "public, max-age=3600",
    ),
    "/static/evidence-review.mjs": (
        _STATIC_ROOT / "evidence-review.mjs",
        "text/javascript; charset=utf-8",
        "public, max-age=3600",
    ),
    "/static/vendor/pdfjs/6.2.108/pdf.min.mjs": (
        _PDFJS_ROOT / "pdf.min.mjs",
        "text/javascript; charset=utf-8",
        "public, max-age=31536000, immutable",
    ),
    "/static/vendor/pdfjs/6.2.108/pdf.worker.min.mjs": (
        _PDFJS_ROOT / "pdf.worker.min.mjs",
        "text/javascript; charset=utf-8",
        "public, max-age=31536000, immutable",
    ),
}


class WorkspaceEditorRequestHandler(EditorRequestHandler):
    """Add workspace identity and local visual evidence review to the typed server."""

    def _dispatch_get(self) -> None:
        path = urlsplit(self.path).path
        asset = _STATIC_ASSETS.get(path)
        if asset is not None:
            file_path, content_type, cache = asset
            self._send_bytes(
                HTTPStatus.OK,
                file_path.read_bytes(),
                content_type,
                cache=cache,
            )
            return
        super()._dispatch_get()

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

        fact_id = self._fact_detail_id() if status is HTTPStatus.OK else None
        if fact_id is not None:
            review = EvidenceReviewApplication(self.repository).fact_review(fact_id)
            section = render_fact_evidence_review(review)
            if "</main>" in payload:
                payload = payload.replace("</main>", section + "</main>", 1)
            if "</head>" in payload:
                payload = payload.replace(
                    "</head>",
                    '<link rel="stylesheet" href="/static/evidence-review.css">\n</head>',
                    1,
                )
            if "</body>" in payload:
                payload = payload.replace(
                    "</body>",
                    '<script type="module" src="/static/evidence-review.mjs"></script>\n</body>',
                    1,
                )
        super()._send_html(payload, status)

    def _fact_detail_id(self) -> str | None:
        parts = urlsplit(self.path).path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "facts" and parts[1]:
            return parts[1]
        return None

    def _serve_evidence(self, source_id: str) -> None:
        source = self.repository.load_source(source_id)
        if not source.agent_processing_allowed:
            raise HTTPRequestError(
                HTTPStatus.FORBIDDEN,
                "PDF evidence is blocked by Source license policy: "
                f"{source.license_class.value}.",
            )
        super()._serve_evidence(source_id)

    def _security_headers(self, *, cache: str) -> None:
        self.send_header("Cache-Control", cache)
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'self'; script-src 'self'; "
            "worker-src 'self'; connect-src 'self'; font-src 'self' data:; "
            "img-src 'self' data: blob:; object-src 'none'; form-action 'self'; "
            "frame-ancestors 'none'; base-uri 'none'",
        )
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")


class WorkspaceEditorHTTPServer(EditorHTTPServer):
    def __init__(self, address: tuple[str, int], repository: KnowledgeRepository) -> None:
        ThreadingHTTPServer.__init__(self, address, WorkspaceEditorRequestHandler)
        self.repository = repository
        self.application = WorkbenchApplication(repository)
        self.csrf_token = secrets.token_urlsafe(32)


def create_server(
    repository_root: Path, port: int = DEFAULT_PORT
) -> WorkspaceEditorHTTPServer:
    validation = validate_workspace(repository_root)
    try:
        validate_pdfjs_vendor()
    except PdfJsVendorError as error:
        raise RepositoryError(str(error)) from error
    repository = KnowledgeRepository(validation.root)
    repository.ensure_layout()
    repository.validate_all(require_canonical=True)
    return WorkspaceEditorHTTPServer(("127.0.0.1", port), repository)
