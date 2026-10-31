import copy
import unittest
from pcbknowledge.v2.bootstrap import qualify


def quantity(value):
    return {'value': value, 'unit': 'F', 'conditions': {}, 'basis': 'DATASHEET',
            'evidence': {'source': 'source:synthetic', 'page': 1}}


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.descriptor = {'kind': 'FLOATING_BOOTSTRAP_SUPPLY', 'bootstrap_pin': '6',
                           'switch_pin': '2', 'supply_pin': '3', 'ground_pin': '1',
                           'charge_path': 'INTERNAL_REGULATOR_DIODE',
                           'capacitor_role': 'capacitor.ceramic',
                           'capacitance_nominal': quantity(1e-7),
                           'evidence': [{'source': 'source:synthetic', 'page': 1}]}
        pins = [{'number': n, 'type': t} for n, t in
                [('1', 'GROUND'), ('2', 'POWER_OUT'), ('3', 'POWER_IN'), ('6', 'POWER_IN')]]
        cap = {'roles': ['capacitor.ceramic'], 'pins': [{'number': '1', 'type': 'PASSIVE'},
               {'number': '2', 'type': 'PASSIVE'}], 'parameters': {'capacitance': quantity(1e-7)}}
        self.parts = {'IC': {'pins': pins, 'roles': ['synthetic'],
                            'bootstrap_supplies': [self.descriptor]}, 'CAP': cap}
        self.nets = {('IC', '1'): 'GND', ('IC', '2'): 'SW', ('IC', '3'): 'VIN',
                     ('IC', '6'): 'BOOT', ('CAP', '1'): 'BOOT', ('CAP', '2'): 'SW'}

    def evidence(self, anchor):
        if anchor != {'source': 'source:synthetic', 'page':
            1}:
            raise ValueError('Dangling source/page')

    def run_case(self, powered=None, grounds=None):
        return qualify(self.parts, self.nets, {'VIN'} if powered is None else powered,
                       {'GND'} if grounds is None else grounds, self.evidence)

    def test_exact_valid_pin_only_no_net_promotion(self):
        powered = {'VIN'}
        qualified, receipts = self.run_case(powered)
        self.assertEqual(qualified, {('IC', '6')})
        self.assertEqual(powered, {'VIN'})
        self.assertEqual(receipts[0]['scope'], 'SOURCE_PATH_TOPOLOGY_ONLY')

    def test_wrong_boot_pin_and_type(self):
        self.descriptor['bootstrap_pin'] = '3'
        with self.assertRaises(ValueError):
            self.run_case()

    def test_no_capacitor(self):
        self.parts.pop('CAP')
        with self.assertRaises(ValueError):
            self.run_case()

    def test_wrong_reference_ground_instead_switch(self):
        self.nets['CAP', '2'] = 'GND'
        with self.assertRaises(ValueError):
            self.run_case()

    def test_missing_input_or_ground_source(self):
        for powered, grounds in [(set(), {'GND'}), ({'VIN'}, set()), ({'BOOT'}, {'GND'})]:
            with self.assertRaises(ValueError):
                self.run_case(powered, grounds)

    def test_wrong_cap_value_or_nonceramic(self):
        self.parts['CAP']['parameters']['capacitance']['value'] = 1e-6
        with self.assertRaises(ValueError):
            self.run_case()
        self.parts['CAP']['parameters']['capacitance']['value'] = 1e-7
        self.parts['CAP']['roles'] = ['capacitor.electrolytic']
        with self.assertRaises(ValueError):
            self.run_case()

    def test_unrelated_power_input_on_boot_net(self):
        self.parts['LOAD'] = {'pins': [{'number': '1', 'type': 'POWER_IN'}], 'roles': []}
        self.nets['LOAD', '1'] = 'BOOT'
        with self.assertRaises(ValueError):
            self.run_case()

    def test_dangling_evidence(self):
        self.descriptor['evidence'][0]['page'] = 2
        with self.assertRaises(ValueError):
            self.run_case()

    def test_no_internal_path_or_unrelated_pin_exemption(self):
        self.descriptor['charge_path'] = 'UNSPECIFIED'
        with self.assertRaises(ValueError):
            self.run_case()
        self.parts['IC'].pop('bootstrap_supplies')
        self.assertEqual(self.run_case()[0], set())

    def test_short_and_duplicate_cap(self):
        self.nets['IC', '6'] = 'SW'
        with self.assertRaises(ValueError):
            self.run_case()
        self.nets['IC', '6'] = 'BOOT'
        self.parts['C2'] = copy.deepcopy(self.parts['CAP'])
        self.nets.update({('C2', '1'): 'BOOT', ('C2', '2'): 'SW'})
        with self.assertRaises(ValueError):
            self.run_case()

    def test_reversed_cap_terminals_valid(self):
        self.nets['CAP', '1'], self.nets['CAP', '2'] = 'SW', 'BOOT'
        self.assertEqual(self.run_case()[0], {('IC', '6')})

    def test_unsupplied_other_input_not_circular(self):
        self.parts['IC']['pins'].append({'number': '7', 'type': 'POWER_IN'})
        self.nets['IC', '7'] = 'OTHER'
        with self.assertRaises(ValueError):
            self.run_case()

    def test_malformed_descriptor_collection(self):
        for invalid in [None, [], 'bootstrap', 1]:
            self.parts['IC']['bootstrap_supplies'] = [invalid]
            with self.assertRaises(ValueError):
                self.run_case()

    def test_capacitor_dangling_evidence(self):
        self.parts['CAP']['parameters']['capacitance']['evidence']['page'] = 2
        with self.assertRaises(ValueError):
            self.run_case()

    def test_malformed_descriptor_pin_or_quantity(self):
        original = copy.deepcopy(self.descriptor)
        for key, value in [('bootstrap_pin', []), ('capacitance_nominal', None)]:
            self.parts['IC']['bootstrap_supplies'] = [dict(original, **{key: value})]
            with self.assertRaises(ValueError):
                self.run_case()


if __name__ == '__main__':
    unittest.main()
