"""Frozen unrelated copper is checked after native session import, despite new UUIDs."""
import copy
import unittest
from pcbknowledge.v2.sexpr import parse, dumps
from pcbknowledge.v2.routing_scope import verify_scope_retention
from tests.git_native.test_v2_routing_scope import inputs, sha


class ScopeRetentionTests(unittest.TestCase):
    def test_unaffected_geometry_exact_and_uuid_independent(self):
        _, seed, _, _, receipt, _ = inputs()
        board = parse(seed)
        board.append(['segment', ['start', '5', '2'], ['end', '6', '3'], ['width', '.15'],
                      ['layer', 'B.Cu'], ['net', '3'], ['uuid', 'bulk']])
        seed = dumps(board)
        receipt['output_sha256'] = sha(seed)
        scope = dict(status='PASS', affected_nets=['D', 'N'], seed_sha256=sha(seed))
        final = copy.deepcopy(board)
        final[-1][-1][1] = 'new-native-uuid'
        self.assertEqual(verify_scope_retention(seed, dumps(final), receipt, scope)['unaffected_segments'], 1)
        final[-1][1][1] = '5.001'
        with self.assertRaises(ValueError):
            verify_scope_retention(seed, dumps(final), receipt, scope)


if __name__ == '__main__':
    unittest.main()
