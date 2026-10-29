"""Synthetic v2 catalog tests in an explicitly selected external Git workspace."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from pcbknowledge.git_native.workspace import initialize_workspace, WorkspaceError
from pcbknowledge.serialization import canonical_json
from pcbknowledge.v2.catalog import Catalog, record_path
from pcbknowledge.v2.cli import main
from pcbknowledge.v2.intent import validate_intent
from pcbknowledge.v2.schema import SCHEMA_DIR
from tests.git_native.test_v2_record_contracts import fixtures, quantity

ROOT=Path(__file__).resolve().parents[2]


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'workspace'
        initialize_workspace(self.root,schema_source_root=ROOT,init_git=True)
        self.documents=fixtures()
        self.documents.pop('rule');self.documents.pop('design-intent');self.documents.pop('fab-profile')
        self.documents['source']['license_class']='PUBLIC_REFERENCE'
        self.save()

    def save(self):
        for doc in self.documents.values():
            path=record_path(self.root,doc['id']);path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(canonical_json(doc), encoding='utf-8', newline='\n')

    def load(self):
        return Catalog(self.root,self.root/'schemas')

    def test_external_workspace_closure_and_read_only_queries(self):
        self.assertEqual(len(self.load().records),4)
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        for args in (['v2','validate'],['part','show','part:synthetic'],['part','search','--role','led'],
                     ['package','show','package:synthetic'],['block','show','block:synthetic'],
                     ['block','search','--text','synthetic'],['registry','show','parameters']):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code=main(['--repo',str(self.root),*args])
            self.assertEqual(code,0,output.getvalue());json.loads(output.getvalue())
        after={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

    def test_registry_unit_and_condition_tamper(self):
        for field,value in [('parameters',{'made_up':quantity()}),
                             ('parameters',{'input_voltage':quantity(1,'A')}),
                             ('roles',['fake']),('pins',[{'number':'1','name':'A','type':'FAKE'}])]:
            with self.subTest(field=field):
                old=copy.deepcopy(self.documents['part']);self.documents['part'][field]=value;self.save()
                with self.assertRaises(ValueError):self.load()
                self.documents['part']=old
        self.save()

    def test_reference_and_pin_pad_tamper(self):
        mutations=[lambda:self.documents['part'].update(package='package:missing'),
                   lambda:self.documents['part']['pins'][0].update(number='2'),
                   lambda:self.documents['part']['pins'].append(copy.deepcopy(self.documents['part']['pins'][0])),
                   lambda:self.documents['block']['components'][0].update(select={'part':'part:missing'}),
                   lambda:self.documents['block']['nets'][0]['connect'].append('D.pin:missing'),
                   lambda:self.documents['block']['ports'].append({'name':'ORPHAN','kind':'INPUT'}),
                   lambda:self.documents['part']['pins'][0].update(same_net_as='2')]
        original=copy.deepcopy(self.documents)
        for mutation in mutations:
            self.documents=copy.deepcopy(original);mutation();self.save()
            with self.assertRaises(ValueError):self.load()

    def test_separate_physical_pads_can_share_one_electrical_number(self):
        pad=self.documents['package']['explicit_pads'][0]
        pad['x']=quantity(0,'mm');pad['y']=quantity(0,'mm')
        tab=copy.deepcopy(pad);tab['x']=quantity(2,'mm')
        self.documents['package']['explicit_pads'].append(tab);self.save();self.load()
        tab['x']=quantity(0,'mm');self.save()
        with self.assertRaisesRegex(ValueError,'Overlapping'):self.load()

    def test_independent_agent_and_fabricated_human_verifier(self):
        part=self.documents['part'];part['verification']='AGENT_VERIFIED'
        for actors in ([],['agent:fixture'],['human:fixture']):
            part['provenance']['verified_by']=actors;self.save()
            with self.assertRaises(ValueError):self.load()
        part['provenance']['verified_by']=['agent:independent'];self.save();self.load()
        part['verification']='HUMAN_VERIFIED';self.save()
        with self.assertRaisesRegex(ValueError,'human:'):self.load()

    def test_evidence_page_license_and_cache_tamper(self):
        source=self.documents['source']
        self.assertEqual(self.load().evidence_status(source),'NOT_LOCALLY_VERIFIED')
        for license_class in ('UNKNOWN','RESTRICTED','LICENSED_BLOCKED_FOR_AI'):
            source['license_class']=license_class;self.save()
            with self.assertRaises(ValueError):self.load()
        source['license_class']='PUBLIC_REFERENCE'
        self.documents['part']['pin_evidence']['page']=2;self.save()
        with self.assertRaises(ValueError):self.load()
        self.documents['part']['pin_evidence']['page']=1
        pdf=b'%PDF-1.4\nsynthetic bytes\n';digest=hashlib.sha256(pdf).hexdigest()
        source.update(sha256=digest,bytes=len(pdf));self.save()
        path=self.root/'.pcbknowledge/evidence/sha256'/digest[:2]/(digest+'.pdf')
        path.parent.mkdir(parents=True);path.write_bytes(pdf)
        self.assertEqual(self.load().evidence_status(source),'LOCALLY_VERIFIED')
        path.write_bytes(pdf[:-1]+b'x')
        with self.assertRaises(ValueError):self.load()

    def test_canonical_duplicate_keys_symlinks_and_identity_path(self):
        path=record_path(self.root,'part:synthetic');original=path.read_bytes()
        for payload in (json.dumps(self.documents['part']).encode(),
                        b'{"schema":"pcbknowledge.part.v2","schema":"duplicate"}'):
            path.write_bytes(payload)
            with self.assertRaises(ValueError):self.load()
        path.write_bytes(original);path.rename(path.with_name('wrong.json'))
        with self.assertRaises(ValueError):self.load()
        path.with_name('wrong.json').rename(path)
        target=Path(self.temp.name)/'outside.json';target.write_bytes(original);path.unlink();path.symlink_to(target)
        with self.assertRaises(ValueError):self.load()

    def test_explicit_workspace_never_falls_back(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code=main(['--repo',str(self.root/'missing'),'v2','validate'])
        self.assertEqual(code,2);self.assertEqual(json.loads(output.getvalue())['status'],'ERROR')

    def test_unsupported_calculator_and_constraint_refuse(self):
        self.documents['block']['checks']=[{'calculator':'led_resistor','inputs':{'supply':quantity()},
            'require':{'output':'resistance','operator':'GE','limit':quantity(1,'ohm')}}]
        self.save()
        with self.assertRaisesRegex(ValueError,'inputs must be exactly'):self.load()
        self.documents['block']['checks']=[]
        self.documents['part']['parameters']['voltage_rating']={**quantity(), 'basis':'CALCULATED',
            'calculator':'led_resistor','inputs':{'supply':quantity()}}
        self.save()
        with self.assertRaisesRegex(ValueError,'inputs must be exactly'):self.load()
        self.documents['part']['parameters']['voltage_rating']=quantity()
        self.documents['block']['layout']=[{'kind':'INVENTED','subject':'D'}];self.save()
        with self.assertRaises(ValueError):self.load()
        self.documents['block']['layout']=[{'kind':'PLACE_NEAR','subject':'D','target':'MISSING','max_distance':quantity(1,'mm')}];self.save()
        with self.assertRaises(ValueError):self.load()

    def test_manifest_and_schema_tamper_fail_in_loader(self):
        manifest=self.root/'pcbknowledge.workspace.json';original=manifest.read_bytes()
        value=json.loads(original);value['schema_digest']='0'*64
        manifest.write_text(canonical_json(value), encoding='utf-8', newline='\n')
        with self.assertRaises(WorkspaceError):self.load()
        manifest.write_bytes(original)
        path=next((self.root/'schemas').glob('*.json'));path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(RuntimeError,'digest'):self.load()

    def test_v1_workspace_is_rejected_without_rewrite(self):
        path=self.root/'pcbknowledge.workspace.json';data=json.loads(path.read_bytes())
        data['format']='pcbknowledge-workspace-v1';original=canonical_json(data)
        path.write_text(original, encoding='utf-8', newline='\n')
        with self.assertRaisesRegex(WorkspaceError,'create a v2 workspace'):self.load()
        self.assertEqual(path.read_text(),original)

    def test_selection_must_have_a_satisfying_part(self):
        self.documents['block']['components'][0]['select']={'role':'resistor','match':{}};self.save()
        with self.assertRaisesRegex(ValueError,'Unsatisfiable'):self.load()

    def intent_fixture(self):
        self.documents.pop('block')
        self.documents['part']['roles']=['connector.header']
        mount=copy.deepcopy(self.documents['part']);mount.update(id='part:mount',mpn='SYNTH-MOUNT',roles=['mechanical.mounting-hole'])
        self.documents['mount']=mount
        fab=fixtures()['fab-profile'];self.documents['fab']=fab
        for doc in self.documents.values():
            doc['verification']='AGENT_VERIFIED';doc['provenance']['verified_by']=['agent:independent']
        def resolve(value, key=None):
            if isinstance(value,dict):
                if value.get('status')=='UNKNOWN':return quantity(0 if key=='rotation' else 1, 'deg' if key=='rotation' else 'mm')
                return {k:resolve(v,k) for k,v in value.items()}
            if isinstance(value,list):return [resolve(v) for v in value]
            return value
        self.documents={k:resolve(v) for k,v in self.documents.items()}
        self.documents['fab']['thickness']=quantity(1.6,'mm')
        self.save();record_path(self.root,'block:synthetic').unlink()
        intent=fixtures()['design-intent']
        intent['components'][0]['footprint']='pcbknowledge:synthetic'
        intent['components'].append({'ref':'H1','part':'part:mount','package':'package:synthetic','footprint':'pcbknowledge:synthetic'})
        intent['bom'].append({'part':'part:mount','refs':['H1'],'quantity':1})
        intent['mechanical']['mounting']=[{'ref':'H1','fastener':'M3'}]
        intent['mechanical']['edge_interfaces']=['D1']
        return intent

    def test_intent_closure_and_computed_weakest_verification(self):
        intent=self.intent_fixture();catalog=self.load()
        validate_intent(catalog,intent,bundle_commit='a'*40)
        mutations=[lambda d:d['components'][0].update(package='package:missing'),
                   lambda d:d['components'][0].update(footprint='invented'),
                   lambda d:d['nets'][0]['pins'][0].update(pin='2'),
                   lambda d:d['bom'][0].update(quantity=2),
                   lambda d:d['bom'][0].update(refs=['H1']),
                   lambda d:d.update(verification='HUMAN_VERIFIED'),
                   lambda d:d['mechanical'].update(edge_interfaces=['missing']),
                   lambda d:d['manufacturing'].update(assembly_side='BOTTOM')]
        for mutate in mutations:
            changed=copy.deepcopy(intent);mutate(changed)
            with self.assertRaises(ValueError):validate_intent(catalog,changed,bundle_commit='a'*40)
        with self.assertRaises(ValueError):validate_intent(catalog,intent,bundle_commit='b'*40)
        self.documents['source']['verification']='DRAFT';self.documents['source']['provenance']['verified_by']=[];self.save()
        with self.assertRaisesRegex(ValueError,'DRAFT'):validate_intent(self.load(),intent,bundle_commit='a'*40)

    def test_intent_requires_power_connections_and_decoupling(self):
        intent=self.intent_fixture();self.documents['part']['pins'][0]['type']='POWER_IN';self.save()
        catalog=self.load()
        with self.assertRaisesRegex(ValueError,'decoupling'):validate_intent(catalog,intent,bundle_commit='a'*40)
        self.documents['part']['pins'][0]['type']='INPUT';self.save();catalog=self.load()
        with self.assertRaisesRegex(ValueError,'checks'):validate_intent(catalog,intent,bundle_commit='a'*40)
        intent['checks'].append({'id':'connection:D1:1','result':'PASS'})
        validate_intent(catalog,intent,bundle_commit='a'*40)
        intent['nets']=[]
        with self.assertRaises(ValueError):validate_intent(catalog,intent,bundle_commit='a'*40)
