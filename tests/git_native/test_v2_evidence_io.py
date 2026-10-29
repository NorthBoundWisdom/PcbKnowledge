"""Evidence fetching never replaces authority or routes around access controls."""
import hashlib
import io
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.evidence import (
    DownloadError, MAX_SOURCE_BYTES, add_evidence, download_source, fetch_evidence, public_target,
)


class EvidenceIOTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.payload = b'%PDF-1.7\noriginal synthetic test data\n'
        self.source = {'id': 'source:synthetic', 'license_class': 'PUBLIC_REFERENCE',
                       'url': 'https://example.com/source.pdf', 'bytes': len(self.payload),
                       'sha256': hashlib.sha256(self.payload).hexdigest(), 'media_type': 'application/pdf'}
        self.catalog = Catalog.__new__(Catalog)
        self.catalog.root = self.root
        self.catalog.records = {self.source['id']: self.source}

    def path(self):
        digest = self.source['sha256']
        return self.root / '.pcbknowledge/evidence/sha256' / digest[:2] / (digest + '.pdf')

    def test_matching_fetch_is_atomic_cached_and_never_repeated(self):
        downloader = Mock(return_value=(self.payload, 200))
        result = fetch_evidence(self.catalog, downloader=downloader)
        self.assertEqual(result['status'], 'MATCH')
        self.assertEqual(self.path().read_bytes(), self.payload)
        self.assertFalse(list(self.path().parent.glob('.evidence-*')))
        again = fetch_evidence(self.catalog, self.source['id'], downloader=downloader)
        self.assertTrue(again['results'][0]['cached'])
        downloader.assert_called_once_with(self.source['url'])

    def test_different_bytes_are_kept_aside_without_replacing_expected_cache(self):
        result = fetch_evidence(self.catalog, downloader=lambda _: (b'%PDF-1.7\nnew revision', 200))
        self.assertEqual(result['status'], 'DIFFERENT_BYTES')
        self.assertFalse(self.path().exists())
        alternative = Path(result['results'][0]['path'])
        self.assertIn('different', alternative.parts)
        self.assertEqual(alternative.read_bytes(), b'%PDF-1.7\nnew revision')
        self.assertEqual(self.source['sha256'], hashlib.sha256(self.payload).hexdigest())

    def test_blocked_licenses_do_not_download_or_import(self):
        file_path = self.root / 'manual.pdf'
        file_path.write_bytes(self.payload)
        for license_class in ('UNKNOWN', 'RESTRICTED', 'LICENSED_BLOCKED_FOR_AI'):
            with self.subTest(license_class=license_class):
                self.source['license_class'] = license_class
                downloader = Mock()
                self.assertEqual(fetch_evidence(self.catalog, downloader=downloader)['status'], 'FAILED')
                downloader.assert_not_called()
                self.assertEqual(add_evidence(self.catalog, file_path)['status'], 'FAILED')
                self.assertFalse(self.path().exists())

    def test_http_failure_reports_status_once(self):
        downloader = Mock(side_effect=DownloadError('Access denied', 403))
        result = fetch_evidence(self.catalog, downloader=downloader)
        self.assertEqual(result['results'][0]['http_status'], 403)
        self.assertEqual(result['status'], 'FAILED')
        downloader.assert_called_once()
        self.assertFalse((self.root / '.pcbknowledge').exists())

    def test_manual_add_matches_digest_and_refuses_unknown_or_bad_metadata(self):
        file_path = self.root / 'manual.pdf'
        file_path.write_bytes(b'not an original')
        self.assertEqual(add_evidence(self.catalog, file_path)['status'], 'FAILED')
        file_path.write_bytes(self.payload)
        self.source['bytes'] += 1
        self.assertEqual(add_evidence(self.catalog, file_path)['status'], 'FAILED')
        self.assertFalse(self.path().exists())
        self.source['bytes'] -= 1
        self.assertEqual(add_evidence(self.catalog, file_path)['status'], 'MATCH')

    def test_invalid_existing_cache_and_symlink_are_not_overwritten(self):
        self.path().parent.mkdir(parents=True)
        self.path().write_bytes(b'old')
        downloader = Mock(return_value=(self.payload, 200))
        self.assertEqual(fetch_evidence(self.catalog, downloader=downloader)['status'], 'FAILED')
        self.assertEqual(self.path().read_bytes(), b'old')
        downloader.assert_not_called()
        self.path().unlink()
        outside = self.root / 'outside'
        outside.write_bytes(b'protected')
        self.path().symlink_to(outside)
        self.assertEqual(fetch_evidence(self.catalog, downloader=downloader)['status'], 'FAILED')
        self.assertEqual(outside.read_bytes(), b'protected')

    def test_parent_symlink_and_oversized_payload_are_refused(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.root / '.pcbknowledge').symlink_to(outside, target_is_directory=True)
        result = fetch_evidence(self.catalog, downloader=lambda _: (self.payload, 200))
        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(list(outside.iterdir()), [])
        (self.root / '.pcbknowledge').unlink()
        with patch('pcbknowledge.v2.evidence.MAX_SOURCE_BYTES', 5):
            self.assertEqual(fetch_evidence(self.catalog, downloader=lambda _: (self.payload, 200))['status'], 'FAILED')

    def test_html_saved_bytes_and_unknown_manual_digest(self):
        self.payload = b'<!doctype html><html>Original synthetic capabilities</html>'
        self.source.update(media_type='text/html', sha256=hashlib.sha256(self.payload).hexdigest(),
                           bytes=len(self.payload))
        result = fetch_evidence(self.catalog, downloader=lambda _: (self.payload, 200))
        self.assertEqual(result['status'], 'MATCH')
        self.assertTrue(result['results'][0]['path'].endswith('.html'))
        self.assertEqual(self.catalog.evidence_status(self.source), 'LOCALLY_VERIFIED')


class NetworkPolicyTests(unittest.TestCase):
    def address(self, ip='93.184.216.34'):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 443))]

    def test_private_targets_credentials_and_non_https_refuse(self):
        for url in ('http://example.com/a', 'https://user:secret@example.com/a', 'https://example.com:8443/a'):
            with patch('socket.getaddrinfo') as resolver:
                with self.assertRaises(DownloadError):
                    public_target(url)
                resolver.assert_not_called()
        for ip in ('127.0.0.1', '10.0.0.1', '169.254.169.254', '224.0.0.1'):
            with patch('socket.getaddrinfo', return_value=self.address(ip)):
                with self.assertRaises(DownloadError):
                    public_target('https://example.com/a')

    def response(self, payload=b'%PDF-1.7', status=200, headers=None):
        response = Mock(status=status)
        response.getheader.side_effect = lambda name: (headers or {}).get(name)
        response.read1.side_effect = io.BytesIO(payload).read1
        return response

    def test_redirect_to_private_address_is_not_requested(self):
        responses = [self.address(), self.address('127.0.0.1')]
        connection = Mock(sock=None)
        connection.getresponse.return_value = self.response(status=302, headers={'Location': 'https://private.test/a'})
        with patch('socket.getaddrinfo', side_effect=responses), patch(
                'pcbknowledge.v2.evidence.PublicHTTPSConnection', return_value=connection) as constructor:
            with self.assertRaises(DownloadError):
                download_source('https://example.com/a')
            constructor.assert_called_once()
            connection.close.assert_called_once()

    def test_public_redirect_and_single_bounded_fetch(self):
        first, second = Mock(sock=None), Mock(sock=None)
        first.getresponse.return_value = self.response(status=302, headers={'Location': '/source.pdf'})
        second.getresponse.return_value = self.response(b'%PDF-1.7\nsource')
        with patch('socket.getaddrinfo', return_value=self.address()), patch(
                'pcbknowledge.v2.evidence.PublicHTTPSConnection', side_effect=[first, second]):
            self.assertEqual(download_source('https://example.com/a'), (b'%PDF-1.7\nsource', 200))
        second.request.assert_called_once_with('GET', '/source.pdf', headers={'User-Agent': 'PcbKnowledge evidence/2'})

    def test_access_denial_and_size_limit_have_no_retry(self):
        for response in (self.response(status=403), self.response(headers={'Content-Length': str(MAX_SOURCE_BYTES + 1)})):
            connection = Mock(sock=None)
            connection.getresponse.return_value = response
            with patch('socket.getaddrinfo', return_value=self.address()), patch(
                    'pcbknowledge.v2.evidence.PublicHTTPSConnection', return_value=connection) as constructor:
                with self.assertRaises(DownloadError):
                    download_source('https://example.com/source')
                constructor.assert_called_once()
                response.read1.assert_not_called()

    def test_stream_size_time_and_redirect_loop_refuse(self):
        connection = Mock(sock=None)
        connection.getresponse.return_value = self.response(b'too much data')
        with patch('socket.getaddrinfo', return_value=self.address()), patch(
                'pcbknowledge.v2.evidence.PublicHTTPSConnection', return_value=connection), patch(
                'pcbknowledge.v2.evidence.MAX_SOURCE_BYTES', 5):
            with self.assertRaisesRegex(DownloadError, 'byte limit'):
                download_source('https://example.com/source')
        connection.getresponse.return_value = self.response()
        with patch('socket.getaddrinfo', return_value=self.address()), patch(
                'pcbknowledge.v2.evidence.PublicHTTPSConnection', return_value=connection), patch(
                'pcbknowledge.v2.evidence.time.monotonic', side_effect=[0, 0, 61]):
            with self.assertRaisesRegex(DownloadError, 'time limit'):
                download_source('https://example.com/source')
        connection.getresponse.return_value = self.response(status=302, headers={'Location': '/source'})
        with patch('socket.getaddrinfo', return_value=self.address()), patch(
                'pcbknowledge.v2.evidence.PublicHTTPSConnection', return_value=connection):
            with self.assertRaisesRegex(DownloadError, 'redirect loop'):
                download_source('https://example.com/source')

    def test_connection_pins_public_address_and_keeps_tls_hostname(self):
        from pcbknowledge.v2.evidence import PublicHTTPSConnection
        raw_socket = Mock()
        context = Mock()
        with patch('socket.socket', return_value=raw_socket), patch('ssl.create_default_context', return_value=context):
            connection = PublicHTTPSConnection('example.com', self.address()[0])
            connection.connect()
        raw_socket.connect.assert_called_once_with(('93.184.216.34', 443))
        context.wrap_socket.assert_called_once_with(raw_socket, server_hostname='example.com')
