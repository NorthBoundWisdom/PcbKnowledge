"""Explicit, bounded import of source originals into the selected local cache."""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import os
from pathlib import Path
import socket
import ssl
import tempfile
import time
from urllib.parse import urljoin, urlsplit

from .catalog import ELIGIBLE

MAX_SOURCE_BYTES = 32 * 1024 * 1024
REQUEST_TIMEOUT = 20
MAX_REDIRECTS = 5
DOWNLOAD_TIMEOUT = 60


class DownloadError(ValueError):
    """A single download failed without an access-control workaround."""

    def __init__(self, reason, http_status=None):
        super().__init__(reason)
        self.http_status = http_status


def public_target(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.fragment or parsed.port not in (None, 443)):
        raise DownloadError('Source URL must be credential-free HTTPS on port 443')
    answers = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    addresses = [ipaddress.ip_address(item[4][0]) for item in answers]
    if not addresses or any(not address.is_global or address.is_multicast for address in addresses):
        raise DownloadError('Source target must resolve only to public addresses')
    return parsed, answers[0]


class PublicHTTPSConnection(http.client.HTTPSConnection):
    """Connect to the validated address while verifying TLS for the original host."""

    def __init__(self, hostname, address):
        super().__init__(hostname, timeout=REQUEST_TIMEOUT, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        family, kind, protocol, _, address = self.address
        connection = socket.socket(family, kind, protocol)
        connection.settimeout(self.timeout)
        try:
            connection.connect(address)
            self.sock = self._context.wrap_socket(connection, server_hostname=self.host)
        except BaseException:
            connection.close()
            raise


def _read_response(response, connection, deadline):
    chunks = []
    size = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DownloadError('Source download exceeded the time limit')
        if connection.sock is not None:
            connection.sock.settimeout(min(REQUEST_TIMEOUT, remaining))
        chunk = response.read1(min(65536, MAX_SOURCE_BYTES + 1 - size))
        if not chunk:
            return b''.join(chunks)
        chunks.append(chunk)
        size += len(chunk)
        if size > MAX_SOURCE_BYTES:
            raise DownloadError('Source response exceeds the byte limit', response.status)


def download_source(url):
    """Fetch once, following normal HTTPS redirects without retrying a failure."""
    visited = set()
    deadline = time.monotonic() + DOWNLOAD_TIMEOUT
    for _ in range(MAX_REDIRECTS + 1):
        if url in visited:
            raise DownloadError('Source redirect loop')
        visited.add(url)
        parsed, address = public_target(url)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DownloadError('Source download exceeded the time limit')
        connection = PublicHTTPSConnection(parsed.hostname, address)
        connection.timeout = min(REQUEST_TIMEOUT, remaining)
        target = parsed.path or '/'
        if parsed.query:
            target += '?' + parsed.query
        try:
            connection.request('GET', target, headers={'User-Agent': 'PcbKnowledge evidence/2'})
            response = connection.getresponse()
            status = response.status
            if status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if not location:
                    raise DownloadError('Redirect has no location', status)
                url = urljoin(url, location)
                continue
            if status != 200:
                raise DownloadError('Source server refused or failed the request', status)
            length = response.getheader('Content-Length')
            if length is not None and (not length.isdecimal() or int(length) > MAX_SOURCE_BYTES):
                raise DownloadError('Source response exceeds the byte limit', status)
            return _read_response(response, connection, deadline), status
        finally:
            connection.close()
    raise DownloadError('Too many source redirects')


def _suffix(source):
    return '.html' if source.get('media_type') == 'text/html' else '.pdf'


def _cache_path(root, digest, suffix, different=False):
    directory = 'different' if different else 'sha256'
    return root / '.pcbknowledge' / 'evidence' / directory / digest[:2] / (digest + suffix)


def _safe_path(root, path):
    if not path.is_relative_to(root):
        raise ValueError('Evidence path escapes the selected workspace')
    for candidate in (path, *path.parents):
        if candidate == root:
            break
        if candidate.is_symlink():
            raise ValueError('Evidence cache paths must not contain symlinks')


def _same_bytes(path, payload):
    if not path.is_file() or path.stat().st_size != len(payload):
        return False
    with path.open('rb') as source:
        return source.read(len(payload) + 1) == payload


def _store(root, path, payload):
    _safe_path(root, path)
    if path.exists():
        if not _same_bytes(path, payload):
            raise ValueError('Existing evidence is different; it will not be overwritten')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _safe_path(root, path)
    descriptor, temporary = tempfile.mkstemp(prefix='.evidence-', dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        _safe_path(root, path)
        # An atomic hard link is create-only: a concurrent writer cannot be replaced.
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.is_symlink() or not _same_bytes(path, payload):
                raise ValueError('Concurrent evidence differs; existing file preserved') from None
    finally:
        temporary.unlink(missing_ok=True)


def _signature_matches(source, payload):
    if source.get('media_type') == 'text/html':
        prefix = payload[:4096].lower()
        return b'<html' in prefix or b'<!doctype html' in prefix
    return payload.startswith(b'%PDF-')


def _accept(catalog, source, payload, http_status=None):
    if len(payload) > MAX_SOURCE_BYTES:
        raise ValueError('Source exceeds the byte limit')
    digest = hashlib.sha256(payload).hexdigest()
    matches = digest == source['sha256']
    path = _cache_path(catalog.root, digest, _suffix(source), different=not matches)
    if matches and (len(payload) != source['bytes'] or not _signature_matches(source, payload)):
        raise ValueError('Recorded source size or media signature is inconsistent')
    _store(catalog.root, path, payload)
    result = {'source': source['id'], 'status': 'MATCH' if matches else 'DIFFERENT_BYTES',
              'sha256': digest, 'path': str(path)}
    if http_status is not None:
        result['http_status'] = http_status
    return result


def _failed(source, error):
    result = {'source': source['id'], 'status': 'FAILED', 'reason': str(error)}
    status = getattr(error, 'http_status', None)
    if status is not None:
        result['http_status'] = status
    return result


def _summary(results):
    statuses = {result['status'] for result in results}
    status = 'MATCH'
    if 'FAILED' in statuses:
        status = 'FAILED'
    elif 'DIFFERENT_BYTES' in statuses:
        status = 'DIFFERENT_BYTES'
    return {'status': status, 'results': results}


def fetch_evidence(catalog, source_id=None, *, downloader=None):
    """Fetch missing eligible originals; blocked, changed or failed bytes stay explicit."""
    download = downloader or download_source
    sources = [catalog.get(source_id, 'source')] if source_id else catalog.search('source')
    results = []
    for source in sources:
        try:
            if source['license_class'] not in ELIGIBLE:
                raise PermissionError('Source license blocks processing')
            if catalog.evidence_status(source) == 'LOCALLY_VERIFIED':
                results.append({'source': source['id'], 'status': 'MATCH', 'cached': True})
                continue
            payload, status = download(source['url'])
            results.append(_accept(catalog, source, payload, status))
        except (OSError, ValueError, http.client.HTTPException) as error:
            results.append(_failed(source, error))
    return _summary(results)


def add_evidence(catalog, file_path):
    """Accept a manually selected original only for an eligible recorded digest."""
    path = Path(file_path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError('Manual source must be a regular file within the byte limit')
    with path.open('rb') as source_file:
        payload = source_file.read(MAX_SOURCE_BYTES + 1)
    if len(payload) > MAX_SOURCE_BYTES:
        raise ValueError('Manual source exceeds the byte limit')
    digest = hashlib.sha256(payload).hexdigest()
    sources = [source for source in catalog.search('source') if source['sha256'] == digest]
    if not sources:
        return {'status': 'FAILED', 'results': [], 'reason': 'File SHA-256 matches no recorded source'}
    results = []
    for source in sources:
        try:
            if source['license_class'] not in ELIGIBLE:
                raise PermissionError('Source license blocks processing')
            results.append(_accept(catalog, source, payload))
        except (OSError, ValueError) as error:
            results.append(_failed(source, error))
    return _summary(results)
