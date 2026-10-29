"""Synthetic shape and rejection tests for the Stage 1 target contracts."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import tempfile
import unittest

from pcbknowledge.v2.schema import ContractSchemas, SCHEMA_DIR, validate as structural_validate
from pcbknowledge.v2.vocabulary import Vocabulary

ROOT = Path(__file__).resolve().parents[2]


def validate(instance, name, directory=None):
    structural_validate(instance, name, directory)
    if directory is None:
        vocabulary = Vocabulary.load(ROOT / 'knowledge/registry', SCHEMA_DIR)
        if name == 'parameters.schema.json':
            vocabulary.parameters(instance)
        else:
            vocabulary.document(instance)


def unknown(query='Q1'):
    return {'status': 'UNKNOWN', 'reason': 'Synthetic input has not been supplied.', 'blocks': [query]}


def quantity(value=1, unit='V'):
    return {'value': value, 'unit': unit, 'conditions': {},
            'basis': 'ENGINEERING_DEFAULT', 'note': 'Synthetic test input.'}


def record(kind, **fields):
    return {'schema': 'pcbknowledge.'+kind+'.v2', 'id': kind+':synthetic',
            'verification': 'DRAFT', 'provenance': {'created_by': 'agent:fixture', 'verified_by': []},
            **fields}


def fixtures():
    evidence = {'source': 'source:synthetic', 'page': 1}
    source = record('source', title='Synthetic source', publisher='Synthetic publisher',
                    revision='A', url='https://example.invalid/source', accessed_on='2026-10-29',
                    sha256='a'*64, bytes=1, pages=1, license_class='UNKNOWN')
    package = record('package', family='EXPLICIT',
        body={key: unknown('Q3') for key in ('length','width','height')},
        footprint={'mode':'EXPLICIT','pads':[{'number':'1','kind':'SMD','shape':'RECT',
            **{key:unknown('Q3') for key in ('x','y','width','height','rotation')}}]},
        pin1='1', courtyard_margin=unknown('Q3'), evidence=[evidence])
    part = record('part', manufacturer='Synthetic maker',mpn='SYNTH-1',package='package:synthetic',
        roles=['led'],pins=[{'number':'1','name':'ANODE','type':'PASSIVE'}],
        parameters={'voltage_rating':quantity()},pin_evidence={'basis':'DATASHEET',**evidence},sourcing={'lifecycle':'UNKNOWN'})
    block = record('block',category='ui.indicator',parameters={'input_voltage':{'quantity':'voltage','required':True}},
        ports=[{'name':'VIN','kind':'POWER_IN'}],components=[{'ref':'D','select':{'role':'led','match':{}}}],
        nets=[{'name':'VIN','connect':['port:VIN','D.pin:ANODE']}],checks=[],layout=[],evidence=[])
    rule = record('rule',applies_to={'pin_type':'POWER_IN'},
        layout=[{'kind':'PLACE_NEAR','subject':'C','target':'U.pin:VDD','max_distance':quantity(2,'mm')}],
        basis='ENGINEERING_DEFAULT',note='Synthetic rule.',evidence=[])
    fab = record('fab_profile',owner_decision='D2',layer_count=2,assembly_side='TOP',
        **{key:unknown('Q9') for key in ('thickness','copper_thickness','trace_width_min','clearance_min',
           'drill_min','annular_ring_min','solder_mask_web_min')},via_types=['THROUGH'],
        stackup=[{'name':str(i),'kind':k,'thickness':unknown('Q9')}
                 for i,k in enumerate(['COPPER','DIELECTRIC','COPPER'])],evidence=[evidence])
    intent={'schema':'pcbknowledge.design_intent.v2','id':'synthetic','brief_id':'G1',
        'bundle_commit':'a'*40,'block_graph_sha256':'b'*64,'status':'EXPANDED',
        'components':[{'ref':'D1','part':'part:synthetic','package':'package:synthetic','footprint':'synthetic.pretty:D1'}],
        'nets':[{'name':'N1','pins':[{'ref':'D1','pin':'1'}],'class':'signal'}],
        'bom':[{'part':'part:synthetic','refs':['D1'],'quantity':1}], 'layout':[],
        'checks':[{'id':'synthetic-check','result':'PASS'}], 'verification':'AGENT_VERIFIED','refusals':[], 'evidence':[]}
    intent.update(fab_profile='fab_profile:synthetic',
        mechanical={'outline_envelope':{'shape':'RECTANGLE','max_length':quantity(50,'mm'),'max_width':quantity(50,'mm')},
            'height_limit':quantity(10,'mm'),'mounting':[{'ref':f'H{i}','fastener':'M3'} for i in range(1,5)],
            'edge_interfaces':['J1']},
        manufacturing={'layers':2,'thickness':quantity(1.6,'mm'),'copper_requirement':'ONE_OZ_NOMINAL','assembly_side':'TOP'})
    return {'source':source,'package':package,'part':part,'block':block,'rule':rule,'fab-profile':fab,'design-intent':intent}


class RecordContractTests(unittest.TestCase):
    def test_every_staged_schema_uses_supported_offline_keywords(self):
        resolver=ContractSchemas()
        for path in sorted(SCHEMA_DIR.glob('*.schema.json')):
            with self.subTest(path=path.name):
                resolver.check(resolver.load(path.name),path.name)

    def test_record_and_intent_positive_shapes(self):
        for kind,instance in fixtures().items():
            with self.subTest(kind=kind):validate(instance,kind+'.schema.json')

    def test_every_record_rejects_missing_envelope_and_unknown_property(self):
        for kind,instance in fixtures().items():
            if kind=='design-intent':continue
            for key in ('schema','id','verification','provenance'):
                mutated=copy.deepcopy(instance);del mutated[key]
                with self.subTest(kind=kind,key=key),self.assertRaises(ValueError):validate(mutated,kind+'.schema.json')
            mutated=copy.deepcopy(instance);mutated['guess']='not in contract'
            with self.assertRaises(ValueError):validate(mutated,kind+'.schema.json')

    def test_quantity_requires_units_structured_conditions_and_basis(self):
        for field in ('unit','conditions','basis','note'):
            data=quantity();del data[field]
            with self.subTest(field=field),self.assertRaises(ValueError):validate(data,'quantity.schema.json')
        for value in ('5 V',True,None):
            data=quantity();data['value']=value
            with self.assertRaises(ValueError):validate(data,'quantity.schema.json')
        for updates in ({'unit':'mV'},{'conditions':'at room temperature'},
                        {'conditions':{'room_temperature':{'value':25,'unit':'degC'}}},
                        {'conditions':{'TA':{'value':25,'unit':'V'}}}, {'min':0}):
            data=quantity();data.update(updates)
            with self.assertRaises(ValueError):validate(data,'quantity.schema.json')

    def test_quantity_range_and_basis_specific_evidence(self):
        data=quantity();del data['value'];data.update(min=1,typ=2,max=3)
        validate(data,'quantity.schema.json')
        for basis,key,value in [('DATASHEET','evidence',{'source':'source:synthetic','page':1}),
                                ('STANDARD_CONVENTION','convention','Synthetic convention'),
                                ('CALCULATED','calculator','led_resistor')]:
            data=quantity();data['basis']=basis
            if basis=='CALCULATED':data['inputs']={'supply':quantity()}
            with self.assertRaises(ValueError):validate(data,'quantity.schema.json')
            data[key]=value;validate(data,'quantity.schema.json')
        data=quantity();data.update(basis='DATASHEET',evidence={'source':'source:synthetic','page':0})
        with self.assertRaises(ValueError):validate(data,'quantity.schema.json')

    def test_unknown_has_explicit_reason_and_consumer_query(self):
        validate(unknown(),'unknown.schema.json')
        for updates in ({'reason':''},{'blocks':[]},{'blocks':['Q13']},{'value':3.3}):
            data=unknown();data.update(updates)
            with self.assertRaises(ValueError):validate(data,'unknown.schema.json')

    def test_parameter_registry_names_and_canonical_units(self):
        validate({'input_voltage':quantity(),'input_current':unknown()},'parameters.schema.json')
        for data in ({'vcc':quantity()},{'input_voltage':quantity(3.3,'A')},{'length':quantity(1,'s')}):
            with self.assertRaises(ValueError):validate(data,'parameters.schema.json')

    def test_registry_files_validate_and_unknown_vocabulary_is_rejected(self):
        for path in sorted((ROOT/'knowledge/registry').glob('*.json')):
            data=json.loads(path.read_text());validate(data,'registry.schema.json')
            data['entries']['invented']={'unexpected':True}
            with self.assertRaises(ValueError):validate(data,'registry.schema.json')

    def test_numeric_ordering_and_parameter_condition_units(self):
        vocabulary = Vocabulary.load(ROOT/'knowledge/registry', SCHEMA_DIR)
        for updates in ({'min':3,'max':1}, {'conditions':{'TA':{'value':25,'unit':'V'}}},
                        {'conditions':{'invented':{'value':1,'unit':'V'}}}):
            data=quantity();data.pop('value');data.update(min=1,max=3);data.update(updates)
            with self.assertRaises(ValueError):vocabulary.parameters({'input_voltage':data})
        documents=[json.loads(p.read_text()) for p in (ROOT/'knowledge/registry').glob('*.json')]
        parameters=next(d for d in documents if d['id']=='registry:parameters')
        parameters['entries']['input_voltage']['conditions']={}
        data=quantity();data['conditions']={'TA':{'value':25,'unit':'degC'}}
        with self.assertRaises(ValueError):Vocabulary(documents).parameters({'input_voltage':data})

    def test_parameter_addition_changes_only_the_registry(self):
        documents = [json.loads(p.read_text()) for p in (ROOT/'knowledge/registry').glob('*.json')]
        parameters = next(d for d in documents if d['id'] == 'registry:parameters')
        parameters['entries']['new_voltage'] = {'quantity':'voltage','conditions':{},'queries':['Q1']}
        structural_validate({'new_voltage':quantity()}, 'parameters.schema.json')
        Vocabulary(documents).parameters({'new_voltage':quantity()})
        with self.assertRaises(ValueError):
            Vocabulary(documents).parameters({'new_voltage':quantity(1,'A')})

    def test_record_pins_roles_packages_license_and_verification_are_typed(self):
        mutations=[('part',lambda d:d['pins'][0].update(type='SUPPLY')),
            ('part',lambda d:d.update(roles=['made-up'])),
            ('part',lambda d:d.update(package='guess-package')),
            ('source',lambda d:d.update(license_class='PUBLIC_SO_APPROVED')),
            ('source',lambda d:d.update(sha256='A'*64)),
            ('source',lambda d:d.update(bytes=True)),
            ('part',lambda d:d.update(verification='APPROVED')),
            ('part',lambda d:d.update(verification='AGENT_VERIFIED'))]
        for kind,change in mutations:
            data=fixtures()[kind];change(data)
            with self.assertRaises(ValueError):validate(data,kind+'.schema.json')

    def test_design_intent_refusal_and_success_states_are_disjoint(self):
        data=fixtures()['design-intent']
        for updates in ({'refusals':[{'code':'UNKNOWN_INPUT','path':'/power','reason':'Missing','queries':['Q11']}]},
                        {'verification':'DRAFT'},{'components':[]},{'checks':[{'id':'x','result':'FAIL'}]},
                        {'checks':[{'id':'x','result':'UNKNOWN'}]}):
            changed=copy.deepcopy(data);changed.update(updates)
            with self.assertRaises(ValueError):validate(changed,'design-intent.schema.json')
        data.update(status='REFUSED',verification='DRAFT',components=[],nets=[],bom=[],
                    refusals=[{'code':'UNKNOWN_INPUT','path':'/power','reason':'Missing input','queries':['Q11']}])
        validate(data,'design-intent.schema.json')
        data['refusals']=[]
        with self.assertRaises(ValueError):validate(data,'design-intent.schema.json')

    def test_rule_basis_requires_the_corresponding_source_or_convention(self):
        data=fixtures()['rule'];data['basis']='DATASHEET'
        with self.assertRaises(ValueError):validate(data,'rule.schema.json')
        data['evidence']=[{'source':'source:synthetic','page':1}]
        validate(data,'rule.schema.json')
        data['basis']='STANDARD_CONVENTION'
        with self.assertRaises(ValueError):validate(data,'rule.schema.json')
        data['convention']='Synthetic convention name'
        validate(data,'rule.schema.json')

    def test_intent_requires_fab_and_board_handoff_fields(self):
        data=fixtures()['design-intent']
        for field in ('fab_profile','mechanical','manufacturing'):
            changed=copy.deepcopy(data);del changed[field]
            with self.assertRaises(ValueError):validate(changed,'design-intent.schema.json')
        mutations=[lambda d:d.update(fab_profile='some-fab'),
            lambda d:d['mechanical']['outline_envelope'].update(max_length=quantity(50,'V')),
            lambda d:d['mechanical']['mounting'][0].update(fastener='guessed'),
            lambda d:d['manufacturing'].update(layers=4),
            lambda d:d['manufacturing'].update(assembly_side='BOTTOM'),
            lambda d:d['manufacturing'].update(copper_requirement='2 oz'),
            lambda d:d['manufacturing'].update(thickness=quantity(1.6,'V'))]
        for mutate in mutations:
            changed=copy.deepcopy(data);mutate(changed)
            with self.assertRaises(ValueError):validate(changed,'design-intent.schema.json')

    def test_refused_intent_preserves_unknown_board_inputs(self):
        data=fixtures()['design-intent']
        data['mechanical']['height_limit']=unknown('Q11')
        with self.assertRaises(ValueError):validate(data,'design-intent.schema.json')
        data.update(status='REFUSED',verification='DRAFT',
            refusals=[{'code':'UNKNOWN_INPUT','path':'/mechanical/height_limit','reason':'Missing input','queries':['Q11']}])
        validate(data,'design-intent.schema.json')
        data['manufacturing']['thickness']=unknown('Q9')
        data['manufacturing']['copper_requirement']=unknown('Q9')
        data['fab_profile']=unknown('Q9')
        validate(data,'design-intent.schema.json')
        del data['manufacturing']['thickness']
        with self.assertRaises(ValueError):validate(data,'design-intent.schema.json')

    def test_mechanical_blocks_have_no_electrical_ports_or_nets(self):
        data=fixtures()['block'];data.update(category='mechanical.mounting',ports=[],nets=[])
        data['components']=[{'ref':'H','select':{'role':'mechanical.mounting-hole','match':{}}}]
        validate(data,'block.schema.json')
        data['ports']=[{'name':'VIN','kind':'POWER_IN'}]
        with self.assertRaises(ValueError):validate(data,'block.schema.json')
        data=fixtures()['block'];data['nets']=[]
        with self.assertRaises(ValueError):validate(data,'block.schema.json')
        data=fixtures()['block'];data['ports']=[]
        with self.assertRaises(ValueError):validate(data,'block.schema.json')

    def test_safe_block_checks_are_structural_not_executable_expressions(self):
        data=fixtures()['block'];data['checks']=[{'calculator':'led_resistor','inputs':{'supply':{'parameter':'input_voltage'}},
            'require':{'output':'resistance','operator':'GE','limit':quantity(0,'ohm')}}]
        validate(data,'block.schema.json')
        data['checks'][0]['require']='__import__("os").system("echo unsafe")'
        with self.assertRaises(ValueError):validate(data,'block.schema.json')

    def test_evaluator_numeric_equality_does_not_confuse_booleans(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'synthetic.schema.json'
            path.write_text(json.dumps({'const':2}))
            validate(2.0,path.name,Path(temp))
            with self.assertRaises(ValueError):validate(True,path.name,Path(temp))
            path.write_text(json.dumps({'type':'array','uniqueItems':True}))
            with self.assertRaises(ValueError):validate([2,2.0],path.name,Path(temp))
            validate([1,True],path.name,Path(temp))
            path.write_text(json.dumps({'type':'integer'}))
            validate(10**400,path.name,Path(temp))

    def test_evaluator_rejects_network_escape_and_unknown_schema_keywords(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'synthetic.schema.json'
            for schema in ({'$ref':'https://example.invalid/schema'}, {'$ref':'../source.schema.json'},
                           {'type':'object','unevaluatedProperties':False}):
                path.write_text(json.dumps(schema))
                with self.assertRaises(ValueError):validate({},path.name,Path(temp))
