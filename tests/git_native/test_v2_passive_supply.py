import unittest
from pcbknowledge.v2 import calculators_passive_paths as MODULE


def fixture():
    return {
        'source_voltage': (4.75, 5.25), 'series_resistance': (.15, .7),
        'current': (0, .1), 'distribution_drop': (0, .05),
        'accepted_output_voltage': (4.63, 5.25),
        'current_limit': (.5, .5), 'current_limit_factor': (1, 1),
    }


class SupplyTests(unittest.TestCase):
    def test_exact_baseline(self):
        result = MODULE.calculate('passive_supply_path', fixture())
        self.assertGreaterEqual(result['voltage_margin'][0], 0)
        self.assertGreaterEqual(result['voltage_drop'][1], .12)
        self.assertAlmostEqual(result['voltage_drop'][1], .12)

    def test_each_physical_input_binds(self):
        for key, value in [('source_voltage', (4.5, 5.25)), ('series_resistance', (.15, 1)),
                           ('current', (0, .5)), ('distribution_drop', (0, .1)),
                           ('accepted_output_voltage', (4.64, 5.25))]:
            inputs = fixture()
            inputs[key] = value
            self.assertLess(MODULE.calculate('passive_supply_path', inputs)['voltage_margin'][0], 0)

    def test_current_rating_and_temperature_factor_bind(self):
        for key, value in [('current_limit', (.05, .05)), ('current_limit_factor', (.1, .1))]:
            inputs = fixture()
            inputs[key] = value
            self.assertLess(MODULE.calculate('passive_supply_path', inputs)['current_margin'][0], 0)
        for value in [(0, 1), (1, 1.1)]:
            inputs = fixture()
            inputs['current_limit_factor'] = value
            with self.assertRaises(ValueError):
                MODULE.calculate('passive_supply_path', inputs)

    def test_negative_or_consumed_source_refuses(self):
        for key, value in [('current', (-1, 1)), ('distribution_drop', (5, 6))]:
            inputs = fixture()
            inputs[key] = value
            with self.assertRaises(ValueError):
                MODULE.calculate('passive_supply_path', inputs)


if __name__ == '__main__':
    unittest.main()
