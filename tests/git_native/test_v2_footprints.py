"""Hand-calculated geometry tables and deterministic footprint exports."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from pcbknowledge.v2.footprints import derive_footprint, export_kicad, export_library, footprint_name
from pcbknowledge.v2.schema import validate
from tests.git_native.test_v2_record_contracts import quantity, record, fixtures

ROOT = Path(__file__).resolve().parents[2]


def package(generator, *, count=2, length=1.6, width=.8, height=.5, **dimensions):
    mount_type = {'pin_header': 'THT', 'mechanical_hole': 'MECHANICAL'}.get(generator, 'SMT')
    scope = {'basis': 'DATASHEET', 'mpns': ['SYNTH-1'],
             'evidence': [{'source': 'source:synthetic', 'page': 1}]}
    return record('package', family='CHIP_0603', mount_type=mount_type, scope=scope, body={
        'length': quantity(length, 'mm'), 'width': quantity(width, 'mm'),
        'height': quantity(height, 'mm')}, drawing={
        'pin_count': count, **{k: quantity(v, 'mm') for k, v in dimensions.items()}},
        generator=generator, density='NOMINAL', pin1='1',
        courtyard_margin=quantity(.25, 'mm'), evidence=[{'source':'source:synthetic','page':1}])


class FootprintTests(unittest.TestCase):
    def test_chip_size_family_table(self):
        # Body length across terminations is lead_span. Long axis is x here.
        # span, termination, width -> x center, pad x-size, pad y-size.
        for span, term, body_width, expected in [
            (1.0, .2, .5, (.475, .45, .6)),   # 0402
            (1.6, .3, .8, (.725, .55, .9)),   # 0603
            (2.0, .4, 1.25, (.875, .65, 1.35)), # 0805
            (3.2, .5, 1.6, (1.425, .75, 1.7)), # 1206
            (4.5, .7, 3.2, (1.975, .95, 3.3)), # 1812
        ]:
            with self.subTest(span=span):
                p = package('chip', length=body_width, width=span,
                            lead_span=span, lead_length=term, lead_width=body_width)
                pads = derive_footprint(p)['pads']
                self.assertEqual((pads[1]['x'], pads[1]['width'], pads[1]['height']), expected)
                self.assertEqual(pads[0]['x'], -pads[1]['x'])
                self.assertEqual(pads[0]['number'], '1')

    def test_asymmetric_chip_terminals(self):
        p=package('chip',lead_span=3.2,lead_length=.5,opposite_lead_length=.45,lead_width=1.6)
        pads=derive_footprint(p)['pads']
        self.assertEqual((pads[0]['x'],pads[0]['width']),(-1.425,.75))
        self.assertEqual((pads[1]['x'],pads[1]['width']),(1.45,.7))

    def test_molded_diode_family_table(self):
        for span, term, lead_width, expected in [
            (3.7,.5,.6,(1.7,.9,.7)),  # SOD-123
            (5.6,.8,2.2,(2.5,1.2,2.3)), # SMA
            (5.6,.8,2.2,(2.5,1.2,2.3)), # SMB
        ]:
            p=package('molded_diode',lead_span=span,lead_length=term,lead_width=lead_width)
            pad=derive_footprint(p)['pads'][1]
            self.assertEqual((pad['x'],pad['width'],pad['height']),expected)

    def test_real_soic8_drawing_bounds_table(self):
        # Microchip DS20001203Y p29: span6, foot length.40..1.27,
        # width .31..51 and pitch1.27. Outer3.3, inner1.63 -> center2.465.
        p=json.loads((ROOT/'knowledge/packages/soic-8-sn.json').read_text())
        derived=derive_footprint(p)
        self.assertEqual([(pad['number'],pad['x'],pad['y']) for pad in derived['pads']], [
            ('1',-2.465,-1.905),('2',-2.465,-.635),('3',-2.465,.635),('4',-2.465,1.905),
            ('5',2.465,1.905),('6',2.465,.635),('7',2.465,-.635),('8',2.465,-1.905)])
        self.assertEqual((derived['pads'][0]['width'],derived['pads'][0]['height']),(1.67,.61))
        self.assertEqual(derived['courtyard'],dict(min_x=-3.55,max_x=3.55,min_y=-2.7,max_y=2.7))

    def test_real_sot238_bounds_table(self):
        # INA219 DCN drawing p36: span2.6..3.0, L.3..6,b.22..38,e.65.
        p=json.loads((ROOT/'knowledge/packages/sot-23-8-dcn.json').read_text())
        pads=derive_footprint(p)['pads']
        self.assertEqual((pads[0]['x'],pads[0]['y'],pads[0]['width'],pads[0]['height']),(-1.2,-.975,1.2,.48))
        self.assertEqual(pads[7]['x'],1.2)

    def test_real_sot223_tab_number_and_projection(self):
        # ST LDL1117 package record p15: H6.7..7.3,E3.3..3.7,B1max3.15,e2.3;
        # p3 says tab VOUT, same electrical pin2. Outer3.95,inner1.55.
        p=json.loads((ROOT/'knowledge/packages/sot-223-ldl1117.json').read_text())
        pads=derive_footprint(p)['pads']
        self.assertEqual([p['number'] for p in pads],['1','2','3','2'])
        self.assertEqual((pads[0]['x'],pads[0]['y'],pads[0]['width'],pads[0]['height']),(-2.75,-2.3,2.4,.95))
        self.assertEqual((pads[3]['x'],pads[3]['y'],pads[3]['width'],pads[3]['height']),(2.75,0,2.4,3.25))

    def test_g1_lqfp_nominal_side_extension_and_clearance(self):
        original = json.loads((ROOT / 'knowledge/packages/lqfp-48-stm32.json').read_text())
        geometry = derive_footprint(original)
        self.assertEqual(len(geometry['pads']), 48)
        self.assertEqual(geometry['pads'][0]['height'], .35)
        self.assertAlmostEqual(.5 - geometry['pads'][0]['height'], .15)
        self.assertGreater(geometry['pads'][0]['height'], original['drawing']['lead_width']['max'])
        compact = copy.deepcopy(original)
        compact['density'] = 'COMPACT'
        robust = copy.deepcopy(original)
        robust['density'] = 'ROBUST'
        self.assertEqual(derive_footprint(compact)['pads'][0]['height'], .32)
        self.assertEqual(derive_footprint(robust)['pads'][0]['height'], .42)

    def test_gullwing_variants_and_four_sides(self):
        # Synthetic drawing tables exercise topology, not invented source claims.
        for count in (4,6,8,10,16):
            p=package('gullwing_two_side',count=count,lead_span=4,lead_length=.5,lead_width=.2,pitch=.65)
            pads=derive_footprint(p)['pads']
            self.assertEqual(len(pads),count)
            self.assertEqual(pads[0]['x'],-1.85)
            self.assertAlmostEqual(pads[0]['y'],-(count/2-1)*.325)
        for count in (3,5):
            p=package('gullwing_two_side',count=count,lead_span=3,lead_length=.5,lead_width=.3,pitch=.95)
            if count == 5:
                p['drawing']['opposite_pitch'] = quantity(1.9, 'mm')
            self.assertEqual(len(derive_footprint(p)['pads']),count)
        p=package('gullwing_four_side',count=48,length=7,width=7,lead_span=9,lead_length=.6,lead_width=.27,pitch=.5)
        pads=derive_footprint(p)['pads']
        self.assertEqual((pads[0]['x'],pads[0]['y']),(-4.3,-2.75))
        self.assertEqual((pads[12]['x'],pads[12]['y']),(-2.75,4.3))
        self.assertEqual((pads[24]['x'],pads[24]['y']),(4.3,2.75))
        self.assertEqual((pads[36]['x'],pads[36]['y']),(2.75,-4.3))
        self.assertEqual((pads[0]['width'],pads[0]['height']),(1,.35))

    def test_crystal_header_and_mechanical_table(self):
        crystal=package('crystal_four_pad',count=4,length=2.5,width=3.2,pitch=2.2,row_pitch=1.6,pad_width=1.0,pad_height=.8)
        pads=derive_footprint(crystal)['pads']
        self.assertEqual([(p['x'],p['y']) for p in pads],[(-1.1,.8),(1.1,.8),(1.1,-.8),(-1.1,-.8)])
        self.assertEqual((pads[0]['width'],pads[0]['height']),(1.1,1.2))
        header=package('pin_header',count=6,length=7.62,width=5.08,pitch=2.54,row_pitch=2.54,drill=1)
        header['drawing']['row_count']=2
        pads=derive_footprint(header)['pads']
        self.assertEqual((pads[0]['x'],pads[0]['y'],pads[0]['width'],pads[0]['drill']),(-1.27,-2.54,1.6,1))
        self.assertEqual((pads[5]['x'],pads[5]['y']),(1.27,2.54))
        hole=package('mechanical_hole',count=1,length=6,width=6,drill=3.2)
        self.assertEqual(derive_footprint(hole)['pads'][0]['kind'],'MECHANICAL')

    def test_explicit_pads_and_rotation(self):
        p=package('chip',lead_span=1.6,lead_length=.3,lead_width=.8)
        for key in ('drawing','generator','density'):del p[key]
        p['explicit_pads']=[dict(number='1',kind='SMD',shape='RECT',x=quantity(0,'mm'),y=quantity(0,'mm'),
            width=quantity(2,'mm'),height=quantity(1,'mm'),rotation=quantity(90,'deg'))]
        self.assertEqual(derive_footprint(p)['courtyard']['min_y'],-1.25)
        validate(p,'package.schema.json')
        p['drawing']={'pin_count':1}
        with self.assertRaises(ValueError):validate(p,'package.schema.json')
        with self.assertRaises(ValueError):derive_footprint(p)

    def test_rejects_missing_unknown_wrong_units_overlaps_and_bad_counts(self):
        p=package('chip',lead_span=1.6,lead_length=.3,lead_width=.8)
        for mutate in (lambda d:d['drawing'].update(pin_count=3),
                       lambda d:d['drawing']['lead_span'].update(unit='V'),
                       lambda d:d['drawing'].pop('lead_length'),
                       lambda d:d['drawing']['lead_length'].update(value=2),
                       lambda d:d.update(pin1='3'),
                       lambda d:d['courtyard_margin'].update(value=-1)):
            candidate=copy.deepcopy(p);mutate(candidate)
            with self.assertRaises(ValueError):derive_footprint(candidate)
        del p['drawing'];del p['generator'];del p['density']
        with self.assertRaises(ValueError):derive_footprint(p)

    def test_explicit_oval_slots_and_rotated_hole_fit(self):
        p=fixtures()['package']
        pad=p['explicit_pads'][0]
        pad.update(kind='THROUGH_HOLE',shape='OVAL',width=quantity(1,'mm'),height=quantity(2,'mm'),
                   drill_width=quantity(.6,'mm'),drill_height=quantity(1.7,'mm'),rotation=quantity(90,'deg'))
        validate(p,'package.schema.json')
        self.assertIn('(drill oval 0.6 1.7)',export_kicad(p))
        self.assertEqual(derive_footprint(p)['pads'][0]['rotation'],90)
        pad['drill']=quantity(.5,'mm')
        with self.assertRaises(ValueError):derive_footprint(p)
        del pad['drill']; del pad['drill_height']
        with self.assertRaises(ValueError):derive_footprint(p)
        pad['drill_height']=quantity(2.1,'mm')
        with self.assertRaises(ValueError):derive_footprint(p)

    def test_library_name_collision_fails_before_writing(self):
        a=package('chip',lead_span=1.6,lead_length=.3,lead_width=.8)
        b=copy.deepcopy(a);a['id']='package:a/b';b['id']='package:a_b'
        self.assertEqual(footprint_name(a),'a_b')
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp).resolve()/'test.pretty'
            with self.assertRaisesRegex(ValueError,'collision'):export_library([a,b],output)
            self.assertFalse(output.exists())

    def test_library_rejects_output_symlinks(self):
        p=package('chip',lead_span=1.6,lead_length=.3,lead_width=.8)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve(); outside=root/'authority';outside.write_text('unchanged')
            folder=root/'test.pretty';folder.mkdir()
            (folder/'synthetic.kicad_mod').symlink_to(outside)
            with self.assertRaisesRegex(ValueError,'Unsafe'):export_library([p],folder)
            self.assertEqual(outside.read_text(),'unchanged')
            (root/'linked.pretty').symlink_to(folder,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'symlinks'):export_library([p],root/'linked.pretty')

    def test_export_is_deterministic_structure_coordinates_and_nonmutating(self):
        p=json.loads((ROOT/'knowledge/packages/sot-223-ldl1117.json').read_text())
        before=copy.deepcopy(p);text=export_kicad(p)
        self.assertEqual(text,export_kicad(p));self.assertEqual(p,before)
        self.assertEqual(text.count('(pad '),4)
        self.assertEqual(text.count('(pad "2"'),2)
        self.assertIn('(at -2.75 -2.3 0)',text)
        self.assertIn('(layer "F.CrtYd")',text)
        with tempfile.TemporaryDirectory() as directory:
            paths=export_library([p],Path(directory).resolve())
            self.assertEqual(paths[0].read_text(),text)
