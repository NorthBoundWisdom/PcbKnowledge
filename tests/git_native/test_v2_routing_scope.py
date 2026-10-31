"""Only native fixed-state tokens change outside authenticated displaced nets."""
import copy
import hashlib
import json
import unittest
from pcbknowledge.v2.sexpr import Atom, dumps, parse
from pcbknowledge.v2.specctra import read_specctra
from pcbknowledge.v2.reservation_protection import protect_seed
from pcbknowledge.v2.routing_scope import freeze_unaffected
from tests.git_native.test_v2_reservation_protection import fixture


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def inputs():
    _, dsn, receipt = fixture()
    removed=['segment',['start','8','8'],['end','9','9'],['width','.3'],
             ['layer','F.Cu'],['net','2'],['uuid','removed']]
    source=['kicad_pcb',['net','0',''],['net','1','N'],['net','2','D'],['net','3','U'],
            ['footprint','P',['pad','1',['net','1','N'],['uuid','pad-a']],
             ['pad','2',['net','1','N'],['uuid','pad-b']]],removed]
    seed=[n for n in source if n != removed]+receipt['seed_nodes']
    source,seed=dumps(source),dumps(seed)
    baseline=json.dumps({'drc_status':'FAIL','exit_code':5,'finding_count':1,
        'report':{'violations':[],'schematic_parity':[],
                  'unconnected_items':[{'items':[{'uuid':'pad-a'},{'uuid':'pad-b'}]}]}})
    receipt.update(output_sha256=sha(seed),current_sha256=sha(source),baseline_drc_sha256=sha(baseline),
                   removed=[{'uuid':'removed','net':'D','node':removed}])
    dsn[3].extend([['net','D'],['net','U']])
    dsn[-1][2][-2][1]='U'
    dsn[-1].append(['wire',['path','B.Cu','300','3000','-5000','6000','-5000'],['net','D'],['type','normal']])
    for row in dsn[-1][1:]:
        row[-1][1]=Atom(row[-1][1])
    text=dumps(dsn)
    protected,proof=protect_seed(text,seed,receipt,expected_board_sha256=sha(seed),expected_dsn_sha256=sha(text))
    return protected,seed,source,baseline,receipt,proof


def call(values):
    return freeze_unaffected(*values,expected_dsn_sha256=sha(values[0]))


class ScopeTests(unittest.TestCase):
    def test_exact_type_only_projection(self):
        values=inputs()
        output,receipt=call(values)
        expected=read_specctra(values[0])
        expected[-1][2][-1][1]='protect'
        self.assertEqual(read_specctra(output),expected)
        self.assertEqual(receipt['affected_nets'],['D','N'])
        self.assertEqual(receipt['per_net']['U']['frozen'],1)
        self.assertEqual(receipt['per_net']['D']['movable'],1)
        self.assertEqual(receipt['per_net']['N']['preserved_fixed'],2)

    def test_source_and_removed_geometry_tampering_rejected(self):
        for index in (1,2,3):
            values=list(inputs())
            values[index]+=' '
            with self.assertRaises(ValueError):
                call(values)
        values=list(inputs())
        values[4]['removed'][0]['node'][1][1]='99'
        with self.assertRaises(ValueError):
            call(values)

    def test_baseline_outside_scope_or_malformed_rejected(self):
        values=list(inputs())
        report=json.loads(values[3])
        report['report']['unconnected_items'][0]['items'][0]['uuid']='unknown'
        values[3]=json.dumps(report)
        values[4]['baseline_drc_sha256']=sha(values[3])
        with self.assertRaises(ValueError):
            call(values)

    def test_unknown_missing_duplicate_types_and_nets_rejected(self):
        for token in ('(type unknown)','(type)','(type normal)(type normal)'):
            values=list(inputs())
            values[0]=values[0].replace('("type" normal)',token,1)
            values[5]['output_dsn_sha256']=sha(values[0])
            with self.assertRaises(ValueError):
                call(values)
        values=list(inputs())
        values[0]=values[0].replace('"U"','"UNKNOWN"')
        values[5]['output_dsn_sha256']=sha(values[0])
        with self.assertRaises(ValueError):
            call(values)

    def test_seed_protection_proof_is_required(self):
        values=list(inputs())
        values[5]['source_board_sha256']='wrong'
        with self.assertRaises(ValueError):
            call(values)


    def test_existing_fixed_states_never_weakened(self):
        for state in ('protect','fix','shoveFixed','shove_fixed'):
            values=list(inputs())
            values[0]=values[0].replace('("type" normal)','("type" '+state+')',1)
            values[5]['output_dsn_sha256']=sha(values[0])
            output,proof=call(values)
            self.assertEqual(read_specctra(output),read_specctra(values[0]))
            self.assertEqual(proof['per_net']['U']['preserved_fixed'],1)

    def test_locked_source_copper_rejected(self):
        values=list(inputs())
        tree=parse(values[2])
        tree[-1].append(Atom('locked'))
        values[2]=dumps(tree)
        values[4]['current_sha256']=sha(values[2])
        with self.assertRaisesRegex(ValueError,'Locked'):
            call(values)


if __name__=='__main__':
    unittest.main()
