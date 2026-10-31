import unittest
from pcbknowledge.v2 import calculators_passive_paths as MODULE


def fixture():
    return {
        **{f'preload_{i}': (990, 1010) for i in range(1, 5)},
        'supply_voltage': (3.17, 3.43), 'tcr_magnitude': (0, .0002),
        'temperature_excursion': (0, 15), 'consumer_1': (.017, .017),
        'consumer_2': (.006, .006), 'consumer_3': (.005, .005),
        'consumer_4': (.005, .005), 'total_budget': (.05, .05),
        'minimum_load': (.01, .01),
    }


class LedgerTests(unittest.TestCase):
    def test_baseline(self):
        result = MODULE.calculate('four_preload_four_consumer_budget', fixture())
        self.assertGreater(result['budget_margin'][0], 0)
        self.assertGreater(result['minimum_load_margin'][0], 0)
        self.assertEqual(result['total_current'][0], result['preload_current'][0])

    def test_each_consumer_is_counted(self):
        for index in range(1, 5):
            inputs = fixture()
            inputs[f'consumer_{index}'] = (.05, .05)
            self.assertLess(MODULE.calculate('four_preload_four_consumer_budget', inputs)['budget_margin'][0], 0)

    def test_each_actual_preload_is_counted(self):
        baseline = MODULE.calculate('four_preload_four_consumer_budget', fixture())
        for index in range(1, 5):
            inputs = fixture()
            inputs[f'preload_{index}'] = (1980, 2020)
            result = MODULE.calculate('four_preload_four_consumer_budget', inputs)
            self.assertLess(result['preload_current'][0], baseline['preload_current'][0])

    def test_allocations_never_prove_minimum_load(self):
        inputs = fixture()
        for index in range(1, 5):
            inputs[f'preload_{index}'] = (99000, 101000)
        result = MODULE.calculate('four_preload_four_consumer_budget', inputs)
        self.assertLess(result['minimum_load_margin'][0], 0)


if __name__ == '__main__':
    unittest.main()
