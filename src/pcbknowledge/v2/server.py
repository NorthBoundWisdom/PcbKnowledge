"""One loopback-only HTTP server for the read-only v2 catalog."""
from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from pcbknowledge.pdfjs_vendor import PDFJS_STATIC_RELATIVE, validate_pdfjs_vendor
from pcbknowledge.workspace import validate_workspace
from .application import Application
from .catalog import Catalog
from . import views

DEFAULT_PORT = 18080
STATIC_ROOT = Path(__file__).resolve().parents[1] / 'static'
CONTENT_POLICY = (
    "default-src 'none'; script-src 'self'; worker-src 'self'; connect-src 'self'; "
    "style-src 'self'; font-src 'self' blob: data:; img-src 'self' data:; "
    "base-uri 'none'; frame-ancestors 'none'"
)


def _assets():
    assets = {
        '/static/catalog.css': ('catalog.css', 'text/css; charset=utf-8'),
        '/static/catalog.mjs': ('catalog.mjs', 'text/javascript; charset=utf-8'),
    }
    for name in ('pdf.min.mjs', 'pdf.worker.min.mjs'):
        relative = (PDFJS_STATIC_RELATIVE / name).as_posix()
        assets['/static/' + relative] = (relative, 'text/javascript; charset=utf-8')
    return assets


class CatalogHandler(BaseHTTPRequestHandler):
    def reply(self, status, content, content_type='text/html; charset=utf-8'):
        if isinstance(content, str):
            content = content.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        if status == 405:
            self.send_header('Allow', 'GET')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', CONTENT_POLICY)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(content)

    def allowed(self):
        allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        hosts = self.headers.get_all('Host', [])
        origins = self.headers.get_all('Origin', [])
        origin_allowed = not origins or (len(origins) == 1 and origins[0] in {'http://' + h for h in allowed})
        return len(hosts) == 1 and hosts[0] in allowed and origin_allowed

    def _route(self, path):
        application = self.server.application
        if path == '/':
            return self.reply(200, views.index(application.index()))
        for plural, kind in (('parts', 'part'), ('blocks', 'block')):
            prefix = '/' + plural + '/'
            if path.startswith(prefix):
                return self.reply(200, views.record(application.record(path[len(prefix):], kind)))
        if path.startswith('/sources/') and path.endswith('/content'):
            identity = path[len('/sources/'):-len('/content')]
            return self.reply(200, application.evidence(identity), 'application/pdf')
        assets = _assets()
        if path in assets:
            relative, mime = assets[path]
            return self.reply(200, (STATIC_ROOT / relative).read_bytes(), mime)
        return self.reply(404, 'Not found.')

    def do_GET(self):
        if not self.allowed():
            return self.reply(403, 'Loopback Host and Origin required.')
        try:
            parsed = urlsplit(self.path)
            if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
                return self.reply(400, 'Unexpected request target.')
            return self._route(unquote(parsed.path))
        except LookupError:
            return self.reply(404, 'Record not found.')
        except FileNotFoundError:
            return self.reply(404, 'Evidence is NOT_LOCALLY_VERIFIED.')
        except PermissionError:
            return self.reply(403, 'Source processing is blocked.')
        except (ValueError, RuntimeError) as error:
            return self.reply(400, views.page('Validation error', '<p>' + escape(str(error)) + '</p>'))

    def do_POST(self):
        return self.reply(405, 'Read-only catalog.')

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST


def create_server(root: Path, port: int = DEFAULT_PORT):
    root = validate_workspace(root).root
    Catalog(root, root / 'schemas')
    validate_pdfjs_vendor()
    server = ThreadingHTTPServer(('127.0.0.1', port), CatalogHandler)
    server.application = Application(root)
    return server
