"""Exact resistor loading cannot silently exceed a shared rail allocation."""
from copy import deepcopy
from fractions import Fraction
import unittest

from pcbknowledge.v2.calculators_resistor_load import calculate


def inputs():
    return {'supply': (3.17, 3.43), 'allocation': (.0015, .0015),
            'resistance_1': (4653, 4747), 'resistance_2': (4653, 4747),
            'tcr_magnitude': (.0001, .0001), 'temperature_excursion': (15, 15)}


class ResistorLoadTests(unittest.TestCase):
    def test_dual_exact_enclosure_and_zero_lower_not_minimum_load(self):
        output = calculate('dual_resistor_load', inputs())
        exact = 2 * Fraction('3.43') / (Fraction(4653) - Fraction(4747)*Fraction('.0001')*15)
        self.assertGreaterEqual(Fraction(output['current'][1]), exact)
        self.assertEqual(output['current'][0], 0)
        self.assertGreater(output['allocation_margin'][0], 0)

    def test_22k_substitution_fails_allocation(self):
        changed = inputs()
        changed['resistance_1'] = changed['resistance_2'] = (2178, 2222)
        self.assertLess(calculate('dual_resistor_load', changed)['allocation_margin'][0], 0)

    def test_single_led_zero_drop_bound(self):
        changed = inputs()
        del changed['resistance_2']
        changed['resistance_1'] = (990, 1010)
        changed['allocation'] = (.00347, .00347)
        result = calculate('single_resistor_load', changed)
        self.assertGreater(result['allocation_margin'][0], 0)
        self.assertGreater(result['current'][1], 3.43/990)

    def test_every_input_changes_result_or_refuses(self):
        baseline = calculate('dual_resistor_load', inputs())
        for key in inputs():
            changed = deepcopy(inputs())
            changed[key] = tuple(value*1.1 for value in changed[key])
            try:
                self.assertNotEqual(calculate('dual_resistor_load', changed), baseline, key)
            except ValueError:
                pass

    def test_nonpositive_or_thermally_invalid_resistor_refuses(self):
        for value in ((0, 1), (-1, 1)):
            changed = inputs()
            changed['resistance_1'] = value
            with self.assertRaises(ValueError):
                calculate('dual_resistor_load', changed)
        changed = inputs()
        changed['temperature_excursion'] = (10000, 10000)
        with self.assertRaises(ValueError):
            calculate('dual_resistor_load', changed)

    def test_interval_allocation_not_treated_as_minimum_load(self):
        changed = inputs()
        changed['allocation'] = (0, .0015)
        result = calculate('dual_resistor_load', changed)
        self.assertEqual(result['current'][0], 0)
        self.assertGreater(result['allocation_margin'][0], 0)
        changed['allocation'] = (.0001, .0015)
        with self.assertRaises(ValueError):
            calculate('dual_resistor_load', changed)


if __name__ == '__main__':
    unittest.main()
