"""HTTP and view-model checks against an external synthetic Git workspace."""
from __future__ import annotations

import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest

from pcbknowledge.workspace import initialize_workspace
from pcbknowledge.serialization import canonical_json
from pcbknowledge.v2.catalog import record_path
from pcbknowledge.v2.server import create_server
from pcbknowledge.v2.application import Application
from tests.git_native.test_v2_record_contracts import fixtures

ROOT=Path(__file__).resolve().parents[2]


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'workspace'
        self.root = initialize_workspace(
            self.root, schema_source_root=ROOT, init_git=True
        ).validation.root
        self.pdf=b'%PDF-1.4\nsynthetic fixture\n'
        records=fixtures();self.source=records['source']
        self.source.update(media_type='application/pdf',license_class='PUBLIC_REFERENCE',sha256=hashlib.sha256(self.pdf).hexdigest(),bytes=len(self.pdf))
        records['part']['mpn']='<script>unsafe</script>'
        records['package']['scope']['mpns'].append(records['part']['mpn'])
        for kind in ('source','part','package','block'):
            doc=records[kind];path=record_path(self.root,doc['id']);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(canonical_json(doc), encoding='utf-8', newline='\n')
        digest=self.source['sha256'];self.cache=self.root/'.pcbknowledge/evidence/sha256'/digest[:2]/(digest+'.pdf')
        self.cache.parent.mkdir(parents=True);self.cache.write_bytes(self.pdf)
        self.server=create_server(self.root,0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)

    def request(self,path,method='GET',headers=None):
        connection=HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        connection.request(method,path,headers=headers or {})
        response=connection.getresponse();body=response.read();result=response.status,dict(response.getheaders()),body
        connection.close();return result

    def test_parts_and_blocks_use_selected_workspace_and_escape_values(self):
        status,headers,body=self.request('/parts/part%3Asynthetic')
        self.assertEqual(status,200);self.assertIn(str(self.root).encode(),body)
        self.assertIn(b'&lt;script&gt;unsafe&lt;/script&gt;',body);self.assertNotIn(b'<script>unsafe',body)
        self.assertIn(b'PDF p1',body);self.assertIn(b'data-url="/sources/source%3Asynthetic/content"',body)
        self.assertEqual(self.request('/blocks/block%3Asynthetic')[0],200)
        self.assertEqual(self.request('/')[0],200)

    def test_pinned_pdfjs_and_worker_are_served_with_module_mime_and_csp(self):
        for name in ('pdf.min.mjs','pdf.worker.min.mjs'):
            status,headers,body=self.request('/static/vendor/pdfjs/6.2.108/'+name)
            self.assertEqual(status,200);self.assertIn('javascript',headers['Content-Type'])
            self.assertIn("worker-src 'self'",headers['Content-Security-Policy'])
        self.assertEqual(self.request('/static/catalog.mjs')[0],200)

    def test_evidence_bytes_require_exact_identity(self):
        path='/sources/source%3Asynthetic/content'
        status,headers,body=self.request(path)
        self.assertEqual((status,body),(200,self.pdf));self.assertEqual(headers['Content-Type'],'application/pdf')
        self.cache.write_bytes(self.pdf[:-1]+b'x')
        self.assertEqual(self.request(path)[0],400)

    def test_missing_cache_is_reported_without_fallback(self):
        self.cache.unlink()
        status,_,body=self.request('/sources/source%3Asynthetic/content')
        self.assertEqual(status,404);self.assertIn(b'NOT_LOCALLY_VERIFIED',body)

    def test_host_and_origin_are_checked(self):
        for headers in ({'Host':'evil.invalid'}, {'Origin':'https://evil.invalid'},
                        {'Host':'127.0.0.1'}, {'Origin':'null'}):
            self.assertEqual(self.request('/',headers=headers)[0],403)
        origin='http://127.0.0.1:'+str(self.server.server_port)
        self.assertEqual(self.request('/',headers={'Origin':origin})[0],200)

    def test_every_mutation_is_refused_without_record_changes(self):
        path=record_path(self.root,'part:synthetic');before=path.read_bytes()
        for method in ('POST','PUT','PATCH','DELETE'):
            self.assertEqual(self.request('/parts/part%3Asynthetic',method)[0],405)
        self.assertEqual(path.read_bytes(),before)

    def test_retired_routes_and_static_traversal_are_absent(self):
        for path in ('/intake','/facts','/review','/sources/new','/static/../workspace.py','/parts/missing'):
            self.assertEqual(self.request(path)[0],404)

    def test_invalid_workspace_does_not_render_stale_authority(self):
        path=self.root/'pcbknowledge.workspace.json';data=json.loads(path.read_bytes());data['schema_digest']='0'*64
        path.write_text(canonical_json(data), encoding='utf-8', newline='\n')
        self.assertEqual(self.request('/')[0],400)

    def test_block_quantities_use_their_own_evidence_page(self):
        source=record_path(self.root,'source:synthetic');data=json.loads(source.read_bytes());data['pages']=2
        source.write_bytes(canonical_json(data).encode('utf-8'))
        path=record_path(self.root,'block:synthetic');block=json.loads(path.read_bytes())
        block['evidence']=[{'source':'source:synthetic','page':1}]
        quantity={'value':2,'unit':'mm','conditions':{},'basis':'DATASHEET',
                  'evidence':{'source':'source:synthetic','page':2}}
        block['layout']=[{'kind':'PLACE_NEAR','subject':'D','target':'D.pin:ANODE','max_distance':quantity}]
        path.write_bytes(canonical_json(block).encode('utf-8'))
        model=Application(self.root).record('block:synthetic','block')
        row=next(row for row in model['rows'] if row['label']=='layout/0/max_distance')
        self.assertEqual(row['evidence']['page'],2)
        status,_,body=self.request('/blocks/block%3Asynthetic')
        self.assertEqual(status,200);self.assertIn(b'data-page="2"',body)

    def make_html_source(self):
        payload = b'<!doctype html><html><script>window.untrustedExecuted=true</script></html>'
        path = record_path(self.root, 'source:synthetic')
        source = json.loads(path.read_bytes())
        source.update(media_type='text/html', sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))
        source['url'] = 'https://example.invalid/doc?x="onmouseover="unsafe&y=<script>'
        path.write_text(canonical_json(source), encoding='utf-8')
        digest = source['sha256']
        cache = self.root / '.pcbknowledge/evidence/sha256' / digest[:2] / (digest + '.html')
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(payload)
        return source, payload

    def test_html_citations_are_external_escaped_links_never_active_local_html(self):
        source, payload = self.make_html_source()
        status, headers, body = self.request('/parts/part%3Asynthetic')
        self.assertEqual(status, 200)
        self.assertIn(b'Open external HTML source', body)
        self.assertIn(b'&quot;onmouseover=&quot;unsafe&amp;y=&lt;script&gt;', body)
        self.assertIn(source['sha256'].encode(), body)
        self.assertIn(source['accessed_on'].encode(), body)
        self.assertIn(b'rel="noopener noreferrer"', body)
        self.assertNotIn(b'class="evidence"', body)
        self.assertNotIn(b'window.untrustedExecuted', body)
        self.assertIn("default-src 'none'", headers['Content-Security-Policy'])
        status, headers, body = self.request('/sources/source%3Asynthetic/content')
        self.assertEqual(status, 400)
        self.assertNotIn(payload, body)
        self.assertNotIn(b'window.untrustedExecuted', body)
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        for headers in ({'Host': 'evil.invalid'}, {'Origin': 'https://evil.invalid'}):
            self.assertEqual(self.request('/parts/part%3Asynthetic', headers=headers)[0], 403)

    def test_html_license_block_prevents_link_and_content(self):
        self.make_html_source()
        path = record_path(self.root, 'source:synthetic')
        source = json.loads(path.read_bytes())
        source['license_class'] = 'RESTRICTED'
        path.write_text(canonical_json(source), encoding='utf-8')
        status, _, body = self.request('/parts/part%3Asynthetic')
        self.assertEqual(status, 400)
        self.assertIn(b'License blocks source processing', body)
        self.assertNotIn(b'Open external HTML source', body)
        self.assertEqual(self.request('/sources/source%3Asynthetic/content')[0], 400)

    def test_engineering_default_identity_needs_no_source_or_page(self):
        for kind in ('part', 'package'):
            identity = kind + ':mounting-hole-m3-3v2'
            original = record_path(ROOT, identity)
            path = record_path(self.root, identity)
            path.write_bytes(original.read_bytes())
        status, _, body = self.request('/parts/part%3Amounting-hole-m3-3v2')
        self.assertEqual(status, 200)
        self.assertIn(b'No citation (engineering default or unspecified)', body)
