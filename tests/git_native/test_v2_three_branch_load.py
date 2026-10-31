import unittest
from pcbknowledge.v2 import calculators_passive_paths as MODULE


def fixture():
    return {
        **{f'resistance_{i}': (9900, 10100) for i in range(1, 4)},
        'supply': (3.17, 3.43), 'tcr_magnitude': (0, .0002),
        'temperature_excursion': (0, 15), 'base_current': (0, .015),
        'allocation': (.017, .017),
    }


class TripleLoadTests(unittest.TestCase):
    def test_baseline_zero_lower(self):
        result = MODULE.calculate('triple_resistor_load_with_base', fixture())
        self.assertEqual(result['current'][0], 0)
        self.assertGreater(result['allocation_margin'][0], 0)

    def test_each_branch_and_base_binds(self):
        for key in ('resistance_1', 'resistance_2', 'resistance_3', 'base_current', 'allocation'):
            inputs = fixture()
            inputs[key] = ((100, 100) if key.startswith('resistance')
                           else (0, .02) if key == 'base_current' else (.01, .01))
            self.assertLess(MODULE.calculate('triple_resistor_load_with_base', inputs)['allocation_margin'][0], 0)

    def test_budget_is_not_minimum_load(self):
        inputs = fixture()
        inputs['base_current'] = (.015, .015)
        self.assertEqual(MODULE.calculate('triple_resistor_load_with_base', inputs)['current'][0], 0)

    def test_invalid_supply_and_shape(self):
        for key, value in [('supply', (0, 3.3)), ('base_current', (.01, .015)),
                           ('allocation', (.01, .017)), ('resistance_1', (0, 100))]:
            inputs = fixture()
            inputs[key] = value
            with self.assertRaises(ValueError):
                MODULE.calculate('triple_resistor_load_with_base', inputs)


if __name__ == '__main__':
    unittest.main()
