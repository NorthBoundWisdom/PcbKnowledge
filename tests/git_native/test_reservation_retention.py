"""Native UUID churn never substitutes for exact seed copper preservation."""
import copy
import unittest
from pcbknowledge.v2.sexpr import dumps
from pcbknowledge.v2.reservation_protection import verify_seed_retention
from tests.git_native.test_v2_reservation_protection import fixture, digest


class RetentionTests(unittest.TestCase):
    def test_native_uuid_churn_preserves_geometry(self):
        board, _, receipt = fixture()
        text = dumps(board)
        receipt['output_sha256'] = digest(text)
        final = copy.deepcopy(board)
        for node in final[3:]:
            node[-1][1] += '-native'
        self.assertEqual(verify_seed_retention(text, dumps(final), receipt)['status'], 'PASS')

    def test_duplicate_or_missing_copper_rejected(self):
        board, _, receipt = fixture()
        text = dumps(board)
        receipt['output_sha256'] = digest(text)
        for mode in ('duplicate', 'missing', 'width'):
            final = copy.deepcopy(board)
            if mode == 'duplicate':
                extra = copy.deepcopy(final[3])
                extra[-1][1] = 'duplicate'
                final.append(extra)
            elif mode == 'missing':
                final.pop(3)
            else:
                final[3][3][1] = '.14'
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                verify_seed_retention(text, dumps(final), receipt)
