"""Synthetic authenticated bundle and electrical mutation tests."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from pcbknowledge.v2.bundle import Bundle, build_bundle, _tree_oid, _git
from pcbknowledge.workspace import initialize_workspace
from pcbknowledge.v2.intent import electrical_checks
from pcbknowledge.v2.netlist import export_netlist

ROOT = Path(__file__).resolve().parents[2]


class BundleTests(unittest.TestCase):
    def test_real_tree_identity(self):
        entries=[]
        for raw in _git(ROOT,'ls-tree','-rz','HEAD').split(b'\0'):
            if raw:
                meta,path=raw.split(b'\t',1); mode,kind,oid=meta.decode().split()
                entries.append({'path':path.decode(),'mode':mode,'oid':oid})
        self.assertEqual(_tree_oid(entries),_git(ROOT,'rev-parse','HEAD^{tree}').decode().strip())

    def test_commit_pinning_cleanliness_and_tampering(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as output:
            root=Path(temp).resolve()/'workspace'
            output=Path(output).resolve()
            initialize_workspace(root, schema_source_root=ROOT, init_git=True)
            def git(*args):
                return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.STDOUT)
            git('config','user.name','Synthetic');git('config','user.email','synthetic@example.invalid')
            git('add','.');git('commit','-m','Synthetic snapshot')
            cache=root/'.pcbknowledge/evidence/local.pdf'
            cache.parent.mkdir(parents=True,exist_ok=True);cache.write_bytes(b'%PDF-synthetic-private-cache')
            first=build_bundle(root,output);payload=first.read_bytes()
            self.assertNotIn(b'synthetic-private-cache',payload)
            self.assertFalse(any(path.startswith('.pcbknowledge/') for path in json.loads(payload)['files']))
            self.assertEqual(build_bundle(root,output).read_bytes(),payload)
            with Bundle(first) as bundle:
                self.assertEqual(bundle.commit,git('rev-parse','HEAD').decode().strip())
                self.assertEqual(bundle.catalog.records,{})
            data=json.loads(payload)
            path=next(iter(data['files']))
            data['files'][path]+=' '
            with self.assertRaisesRegex(ValueError,'blob'):
                Bundle.from_document(data)
            data=json.loads(payload);data['commit']='a'*40
            with self.assertRaisesRegex(ValueError,'commit identity'):
                Bundle.from_document(data)
            (root/'dirty.txt').write_text('dirty')
            with self.assertRaisesRegex(ValueError,'clean committed'):
                build_bundle(root,output)

    def test_audit_authenticates_original_corpus_graph_and_rejects_orphan(self):
        from pcbknowledge.serialization import canonical_json
        from pcbknowledge.v2.catalog import record_path
        from pcbknowledge.v2.bundle import _selected
        from tests.git_native.test_v2_record_contracts import fixtures, quantity
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as output:
            root = Path(temp).resolve() / 'workspace'
            initialize_workspace(root, schema_source_root=ROOT, init_git=True)
            def git(*args):
                return _git(root, *args)
            git('config', 'user.name', 'Synthetic')
            git('config', 'user.email', 'synthetic@example.invalid')
            records = fixtures()
            records['source']['license_class'] = 'PUBLIC_REFERENCE'
            for kind in ('source', 'package', 'part', 'block'):
                record = records[kind]
                destination = record_path(root, record['id'])
                destination.write_text(canonical_json(record), encoding='utf-8')
            graph = {
                'schema': 'pcbknowledge.block-graph.v2', 'id': 'synthetic', 'brief': 'G1',
                'status': 'DRAFT', 'interface_status': 'PLANNED_BLOCK_CONTRACTS', 'requirements': ['test'],
                'instances': [{'id': identity, 'block': 'block:synthetic',
                    'parameters': {'input_voltage': quantity(1)},
                    'ports': [{'name': 'VIN', 'type': 'POWER_IN'}], 'requirements': ['test']}
                    for identity in ('first', 'second')],
                'connections': [{'net': 'VIN', 'endpoints': [
                    {'instance': identity, 'port': 'VIN'} for identity in ('first', 'second')]}],
            }
            path = root / 'evals/corpus/synthetic/input.json'
            path.parent.mkdir(parents=True)
            path.write_text(canonical_json(graph), encoding='utf-8')
            git('add', '.')
            git('commit', '-m', 'Synthetic original graph')
            result = build_bundle(root, Path(output).resolve())
            with Bundle(result) as bundle:
                self.assertEqual(len(bundle.catalog.records), 4)
            document = json.loads(result.read_bytes())
            self.assertEqual(json.loads(document['files'][path.relative_to(root).as_posix()]), graph)
            # A new authentic commit with the original graph removed is still
            # invalid authority: authentication cannot substitute reachability.
            path.unlink()
            git('add', '.')
            git('commit', '-m', 'Synthetic orphan mutation')
            with self.assertRaisesRegex(ValueError, 'Unreachable catalog records'):
                build_bundle(root, Path(output).resolve())
            commit = git('rev-parse', 'HEAD').decode().strip()
            entries = []
            files = {}
            for raw in git('ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
                if not raw:
                    continue
                metadata, name = raw.split(b'\t', 1)
                mode, _, oid = metadata.decode().split()
                name = name.decode()
                entries.append({'path': name, 'mode': mode, 'oid': oid})
                if _selected(name):
                    files[name] = git('cat-file', 'blob', oid).decode()
            document.update(commit=commit, commit_object=git('cat-file', 'commit', commit).decode(),
                            tree=entries, files=files)
            with self.assertRaisesRegex(ValueError, 'Unreachable catalog records'):
                Bundle.from_document(document)

    def test_unsafe_tree_rejected(self):
        for path in ('../escape','/escape','a/../../escape','.git/config','a\\b'):
            with self.subTest(path=path),self.assertRaises(ValueError):
                _tree_oid([{'path':path,'mode':'100644','oid':'a'*40}])


class ElectricalTests(unittest.TestCase):
    def circuit(self):
        parts={'U':{'roles':['mcu.32-bit'],'pins':[
            {'number':'1','name':'VDD','type':'POWER_IN'},
            {'number':'2','name':'GND','type':'GROUND'},
            {'number':'3','name':'SDA','type':'OPEN_DRAIN'}]},
            'C':{'roles':['capacitor.ceramic'],'pins':[{'number':'1','type':'PASSIVE'},{'number':'2','type':'PASSIVE'}]},
            'R':{'roles':['resistor'],'pins':[{'number':'1','type':'PASSIVE'},{'number':'2','type':'PASSIVE'}]}}
        nets=[{'name':'VDD','pins':[{'ref':'U','pin':'1'},{'ref':'C','pin':'1'},{'ref':'R','pin':'1'}]},
              {'name':'GND','pins':[{'ref':'U','pin':'2'},{'ref':'C','pin':'2'}]},
              {'name':'SDA','pins':[{'ref':'U','pin':'3'},{'ref':'R','pin':'2'}]}]
        return parts,nets

    def test_required_connections_decoupling_and_pullups_recomputed(self):
        parts,nets=self.circuit()
        self.assertTrue(all(c['result']=='PASS' for c in electrical_checks(parts,nets)))
        for ref,pin,expected in [('U','1','connection:'),('C','2','decoupling:'),('R','2','pullup:')]:
            mutated=copy.deepcopy(nets)
            for net in mutated:
                net['pins']=[p for p in net['pins'] if (p['ref'],p['pin'])!=(ref,pin)]
            self.assertTrue(any(c['id'].startswith(expected) and c['result']=='FAIL' for c in electrical_checks(parts,mutated)))

    def test_alias_mutation(self):
        parts,nets=self.circuit()
        parts['U']['pins'].append({'number':'4','name':'GND2','type':'GROUND','same_net_as':'2'})
        nets[0]['pins'].append({'ref':'U','pin':'4'})
        self.assertIn({'id':'alias:U:4','result':'FAIL','reason':'Aliased physical terminals share a net'},electrical_checks(parts,nets))


class ExpansionTests(unittest.TestCase):
    def fixture(self):
        from tests.git_native.test_v2_record_contracts import fixtures, quantity
        from pcbknowledge.v2.catalog import Catalog
        from pcbknowledge.v2.schema import ContractSchemas
        from pcbknowledge.v2.vocabulary import Vocabulary
        records=fixtures()
        source=records['source'];source['license_class']='PUBLIC_REFERENCE'
        package=records['package']
        package.pop('drawing',None);package.pop('generator',None);package.pop('density',None)
        package.update(family='EXPLICIT',explicit_pads=[{'number':str(i),'kind':'SMD','shape':'RECT',
            'x':quantity(i*2,'mm'),'y':quantity(0,'mm'),'width':quantity(1,'mm'),
            'height':quantity(1,'mm'),'rotation':quantity(0,'deg')} for i in (1,2)])
        part=records['part'];part.update(roles=['resistor'],pins=[{'number':str(i),'name':str(i),'type':'PASSIVE'} for i in (1,2)])
        mount=copy.deepcopy(part);mount.update(id='part:mount',mpn='MOUNT',roles=['mechanical.mounting-hole'])
        block=records['block'];block.update(parameters={},ports=[{'name':'A','kind':'PASSIVE'},{'name':'B','kind':'PASSIVE'}],
            components=[{'ref':'R1','select':{'part':part['id']}},{'ref':'H1','select':{'part':mount['id']}}],
            nets=[{'name':'A','connect':['port:A','R1.pin:1']},{'name':'B','connect':['port:B','R1.pin:2']}])
        fab=records['fab-profile']
        def resolve(value):
            if isinstance(value,dict):
                if value.get('status')=='UNKNOWN':return quantity(1,'mm')
                return {key:resolve(child) for key,child in value.items()}
            if isinstance(value,list):return [resolve(child) for child in value]
            return value
        fab=resolve(fab);fab['thickness']=quantity(1.6,'mm')
        catalog=Catalog.__new__(Catalog);catalog.root=ROOT
        catalog.schemas=ContractSchemas(ROOT/'schemas');catalog.vocabulary=Vocabulary.load(ROOT/'knowledge/registry',ROOT/'schemas')
        catalog.records={r['id']:r for r in (source,package,part,mount,block,fab)}
        for record in catalog.records.values():
            record['verification']='AGENT_VERIFIED';record['provenance']['verified_by']=['agent:independent']
        brief=json.loads((ROOT/'evals/golden-designs/g1.brief.json').read_text())
        brief['functions']=[{**brief['functions'][0],'id':'passive','count':2,'category':'ui.indicator','parameters':{}}]
        brief['interfaces']=brief['interfaces'][:1];brief['constraints']=[];brief['mechanical']['mounting']=[]
        brief['mechanical']['edge_interfaces']=[];brief['manufacturing']['profile']=fab['id']
        brief['power']['sources'][0]['function']='passive'
        brief['power']['rails']=[]
        block['parameters']={'output_voltage':{'quantity':'voltage','required':True},
                             'output_current':{'quantity':'current','required':True}}
        graph={'schema':'pcbknowledge.block-graph.v2','id':'synthetic','brief':'G1','status':'DRAFT',
               'interface_status':'PLANNED_BLOCK_CONTRACTS','requirements':['usb'],
               'instances':[{'id':iid,'block':block['id'],'parameters':{'output_voltage':quantity(5),'output_current':quantity(0.5,'A')},
                             'ports':[{'name':name,'type':'PASSIVE'} for name in ('A','B')],
                             'requirements':['passive']} for iid in ('first','second')],
               'connections':[{'net':name,'endpoints':[{'instance':iid,'port':port} for iid in ('first','second')]}
                              for name,port in (('ONE','A'),('TWO','B'))]}
        return catalog,graph,brief

    def test_generic_expansion_is_deterministic_and_exported(self):
        from pcbknowledge.v2.expansion import expand,validate_expansion
        from types import SimpleNamespace
        catalog,graph,brief=self.fixture()
        intent=expand(catalog,graph,brief,bundle_commit='a'*40)
        self.assertEqual(intent['status'],'EXPANDED',intent['refusals'])
        self.assertEqual(intent,expand(catalog,graph,brief,bundle_commit='a'*40))
        self.assertEqual(len(intent['components']),4)
        self.assertIn('block:synthetic',intent['dependencies'])
        bundle=SimpleNamespace(catalog=catalog,briefs={'G1':brief},commit='a'*40)
        validate_expansion(bundle,intent,graph)
        from xml.etree import ElementTree as ET
        root=ET.fromstring(export_netlist(intent,catalog))
        self.assertEqual(len(root.findall('./components/comp')),4)
        self.assertEqual(len(root.findall('./nets/net')),2)
        definitions = {(p.attrib['lib'],p.attrib['part']):p for p in root.findall('./libparts/libpart')}
        self.assertEqual(len(definitions),2)
        for component in root.findall('./components/comp'):
            source = component.find('libsource')
            self.assertIsNotNone(source)
            definition = definitions[source.attrib['lib'],source.attrib['part']]
            self.assertEqual([p.attrib for p in definition.findall('./pins/pin')],
                             [{'num':str(i),'name':str(i),'type':'passive'} for i in (1,2)])
        altered=copy.deepcopy(intent);altered['dependencies'].remove('block:synthetic')
        with self.assertRaisesRegex(ValueError,'deterministic'):
            validate_expansion(bundle,altered,graph)

    def test_graph_mutations_refuse_and_draft_dependency_propagates(self):
        from pcbknowledge.v2.expansion import expand
        catalog,graph,brief=self.fixture()
        for mutation in (lambda g:g['instances'][0]['ports'].pop(),
                         lambda g:g['connections'].pop(),
                         lambda g:g['instances'].pop(),
                         lambda g:g['instances'][0].update(block='block:missing')):
            changed=copy.deepcopy(graph);mutation(changed)
            result=expand(catalog,changed,brief,bundle_commit='a'*40)
            self.assertEqual(result['status'],'REFUSED',result)
        catalog.records['source:synthetic']['verification']='DRAFT'
        result=expand(catalog,graph,brief,bundle_commit='a'*40)
        self.assertEqual(result['verification'],'DRAFT')
        self.assertTrue(any(r['code']=='UNVERIFIED_RECORD' for r in result['refusals']))

    def test_fixed_parameter_mutation_refuses(self):
        from pcbknowledge.v2.expansion import expand
        from tests.git_native.test_v2_record_contracts import quantity
        catalog,graph,brief=self.fixture()
        block=catalog.records['block:synthetic']
        block['parameters']['input_voltage']={'quantity':'voltage','required':True,'fixed':quantity(5)}
        for instance in graph['instances']:
            instance['parameters']['input_voltage']=quantity(5)
        self.assertEqual(expand(catalog,graph,brief,bundle_commit='a'*40)['status'],'EXPANDED')
        graph['instances'][0]['parameters']['input_voltage']=quantity(4)
        result=expand(catalog,graph,brief,bundle_commit='a'*40)
        self.assertEqual(result['status'],'REFUSED')
        self.assertTrue(any('fixed block' in r['reason'] for r in result['refusals']))

    def test_rule_templates_bind_and_join_dependency_closure(self):
        from pcbknowledge.v2.rules import apply_rules
        from tests.git_native.test_v2_record_contracts import record,quantity
        parts,nets=ElectricalTests().circuit()
        catalog,_,_=self.fixture()
        rule=record('rule',applies_to={'pin_type':'POWER_IN'},layout=[{
            'kind':'PLACE_NEAR','subject':'decoupling_capacitor','target':'power_pin',
            'max_distance':quantity(3,'mm')}],basis='ENGINEERING_DEFAULT',note='Synthetic',evidence=[])
        catalog.records[rule['id']]=rule
        layout,used=apply_rules(catalog,parts,nets)
        self.assertEqual(used,{rule['id']})
        self.assertEqual(layout[0]['subject'],'C')
        self.assertEqual(layout[0]['target'],'U.pin:1')
        rule['layout'][0]['subject']='unbound'
        with self.assertRaisesRegex(ValueError,'Unbound'):
            apply_rules(catalog,parts,nets)

    def test_power_ground_short_fails_electrical_checks(self):
        parts,nets=ElectricalTests().circuit()
        nets[0]['pins'].extend(nets.pop(1)['pins'])
        checks=electrical_checks(parts,nets)
        self.assertTrue(any(c['id'].startswith('decoupling:') and c['result']=='FAIL' for c in checks))

    def test_rule_override_requires_block_replacement(self):
        from pcbknowledge.v2.rules import apply_rules
        from tests.git_native.test_v2_record_contracts import record,quantity
        parts,nets=ElectricalTests().circuit()
        catalog,_,_=self.fixture()
        rule=record('rule',applies_to={'pin_type':'POWER_IN'},layout=[{
            'kind':'PLACE_NEAR','subject':'decoupling_capacitor','target':'power_pin',
            'max_distance':quantity(3,'mm')}],basis='ENGINEERING_DEFAULT',note='Synthetic',evidence=[])
        catalog.records[rule['id']]=rule
        parts['U']['overrides']=[{'rule':rule['id'],'replace_with':'block-provided'}]
        with self.assertRaisesRegex(ValueError,'no block-provided'):
            apply_rules(catalog,parts,nets)
        replacement={'kind':'PLACE_NEAR','subject':'C','target':'U.pin:1','max_distance':quantity(2,'mm')}
        layout,used=apply_rules(catalog,parts,nets,[replacement])
        self.assertEqual(layout,[])
        self.assertEqual(used,{rule['id']})

    def test_output_driver_contention_and_alias(self):
        parts={'U':{'roles':[],'pins':[{'number':'1','type':'POWER_OUT'}]},
               'V':{'roles':[],'pins':[{'number':'1','type':'POWER_OUT'}]}}
        nets=[{'name':'RAIL','pins':[{'ref':'U','pin':'1'},{'ref':'V','pin':'1'}]}]
        self.assertTrue(any(c['id']=='drivers:RAIL' and c['result']=='FAIL' for c in electrical_checks(parts,nets)))
        parts['U']['pins'].append({'number':'2','type':'POWER_OUT','same_net_as':'1'})
        nets[0]['pins'][1]={'ref':'U','pin':'2'}
        self.assertTrue(all(c['result']=='PASS' for c in electrical_checks(parts,nets)))

    def test_export_replays_graph_before_writing(self):
        from pcbknowledge.v2.expansion import expand
        from pcbknowledge.v2.netlist import export_design
        from types import SimpleNamespace
        catalog,graph,brief=self.fixture()
        bundle=SimpleNamespace(catalog=catalog,briefs={'G1':brief},commit='a'*40)
        intent=expand(catalog,graph,brief,bundle_commit=bundle.commit)
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory).resolve()/'export'
            changed=copy.deepcopy(intent);changed['layout'].append({'kind':'ORIENTATION','subject':'first_R1','angle':{'value':0,'unit':'deg','conditions':{},'basis':'ENGINEERING_DEFAULT','note':'Synthetic'}})
            with self.assertRaisesRegex(ValueError,'deterministic'):
                export_design(changed,bundle,graph,output)
            self.assertFalse(output.exists())
            export_design(intent,bundle,graph,output)
            self.assertEqual(json.loads((output/'graph.json').read_text()),graph)
            for name in ('graph.json','design-intent.json','design.net'):
                self.assertNotIn(b'\r', (output/name).read_bytes())
            self.assertEqual(json.loads((output/'design-intent.json').read_text()),intent)
            self.assertTrue((output/'pcbknowledge.pretty/synthetic.kicad_mod').is_file())
            self.assertTrue((output/'design.net').is_file())

    def test_function_category_and_power_budget_mutations_refuse(self):
        from pcbknowledge.v2.expansion import expand
        catalog,graph,brief=self.fixture()
        changed=copy.deepcopy(brief);changed['functions'][0]['category']='digital.mcu'
        result=expand(catalog,graph,changed,bundle_commit='a'*40)
        self.assertTrue(any('category' in r['reason'] for r in result['refusals']))
        changed=copy.deepcopy(brief);changed['power']['sources'][0]['current_budget']['value']=0.1
        result=expand(catalog,graph,changed,bundle_commit='a'*40)
        self.assertTrue(any('current_budget' in r['reason'] for r in result['refusals']))

    def test_decoupled_but_unsourced_power_island_refuses(self):
        from pcbknowledge.v2.expansion import expand
        catalog,graph,brief=self.fixture()
        part=catalog.records['part:synthetic']
        part['roles']=['mcu.32-bit']
        part['pins'][0]['type']='POWER_IN';part['pins'][1]['type']='GROUND'
        cap=copy.deepcopy(part);cap.update(id='part:cap',mpn='CAP',roles=['capacitor.ceramic'])
        for pin in cap['pins']:pin['type']='PASSIVE'
        catalog.records[cap['id']]=cap
        block=catalog.records['block:synthetic']
        block['components'].append({'ref':'C1','select':{'part':cap['id']}})
        block['nets'][0]['connect'].append('C1.pin:1');block['nets'][1]['connect'].append('C1.pin:2')
        result=expand(catalog,graph,brief,bundle_commit='a'*40)
        self.assertEqual(result['status'],'REFUSED')
        self.assertTrue(any('board-source path' in r['reason'] for r in result['refusals']))
        self.assertTrue(all(c['result']=='PASS' for c in result['checks'] if c['id'].startswith('decoupling:')))

    def test_export_refuses_existing_file_symlink(self):
        from pcbknowledge.v2.expansion import expand
        from pcbknowledge.v2.netlist import export_design
        from types import SimpleNamespace
        catalog,graph,brief=self.fixture()
        bundle=SimpleNamespace(catalog=catalog,briefs={'G1':brief},commit='a'*40)
        intent=expand(catalog,graph,brief,bundle_commit=bundle.commit)
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory).resolve()/'export';output.mkdir()
            authority=Path(directory).resolve()/'authority';authority.write_text('keep')
            (output/'design.net').symlink_to(authority)
            with self.assertRaisesRegex(ValueError,'symlink'):
                export_design(intent,bundle,graph,output)
            self.assertEqual(authority.read_text(),'keep')
