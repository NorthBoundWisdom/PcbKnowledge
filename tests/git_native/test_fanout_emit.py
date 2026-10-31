import unittest
from pcbknowledge.v2.fanout_emit import append_copper
from test_fanout_solver import candidate
from pcbknowledge.v2.sexpr import parse


class EmitTests(unittest.TestCase):
    def test_source_nodes_preserved_and_exact_added_dimensions(self):
        source='(kicad_pcb (net 0 "") (net 1 "SIGNAL") (zone (net 1) (layer "B.Cu")))'
        allocation={'synthetic':candidate('SIGNAL',[1,1],[1,3])}
        text,receipt=append_copper(source,allocation)
        self.assertEqual(parse(text)[:len(parse(source))],parse(source))
        self.assertEqual(receipt['added_vias'],1)
        self.assertEqual(receipt['added_segments'],1)
        self.assertEqual((text,receipt),append_copper(source,allocation))

    def test_preexisting_copper_and_unknown_net_rejected(self):
        for source in ['(kicad_pcb (net 1 "SIGNAL") (segment))','(kicad_pcb (net 1 "OTHER"))']:
            with self.assertRaises(ValueError):append_copper(source,{'x':candidate('SIGNAL',[0,0],[0,2])})

if __name__=='__main__':unittest.main()
