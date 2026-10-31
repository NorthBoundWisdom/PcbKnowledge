import unittest
from pcbknowledge.v2.fanout_requests import extract_requests

BOARD='''(kicad_pcb (net 0 "") (net 1 "SIG")
(footprint "synthetic" (property "Reference" "U1")
(pad "1" smd rect (uuid "p1") (net 1 "SIG"))
(pad "2" thru_hole circle (uuid "p2") (net 1 "SIG")))
(segment (uuid "track")))'''


def report(*ids):
    return {'report':{'unconnected_items':[{'type':'unconnected_items','items':[{'uuid':i} for i in ids]}]}}


class ExtractTests(unittest.TestCase):
    def test_select_pad_once_preserve_exclusions(self):
        r=extract_requests(BOARD,report('p1','p1','p2','track'))
        self.assertEqual(r['requests'],[dict(uuid='p1',reference='U1',pad='1',net='SIG')])
        self.assertEqual(len(r['excluded_pads']),1);self.assertEqual(r['nonpad_items'],['track'])

    def test_unknown_uuid_not_guessed_from_prose(self):
        with self.assertRaises(ValueError):extract_requests(BOARD,report('absent'))

if __name__=='__main__':unittest.main()
