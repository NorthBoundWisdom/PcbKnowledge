"""Selected parallel capacitance bounds and real dispatcher bindings."""
import unittest

from pcbknowledge.v2 import calculators_passive_paths as MODULE


def fixture(count):
    return {
        **{f'capacitance_{i}': (90e-9, 110e-9) for i in range(1, count + 1)},
        'retained_lower_factor': (.5, .5), 'positive_upper_factor': (1.15, 1.15),
        'required_window': (150e-9, 1e-6),
    }


class CapacitanceTests(unittest.TestCase):
    def test_quad_passes_dual_fails(self):
        quad = MODULE.calculate('quad_parallel_capacitance', fixture(4))
        dual = MODULE.calculate('dual_parallel_capacitance', fixture(2))
        self.assertGreater(quad['window_margin'][0], 0)
        self.assertLess(dual['window_margin'][0], 0)
        self.assertLessEqual(quad['effective_capacitance'][0], 180e-9)
        self.assertGreaterEqual(quad['effective_capacitance'][1], 506e-9)

    def test_each_actual_component_binds(self):
        for index in range(1, 5):
            inputs = fixture(4)
            inputs[f'capacitance_{index}'] = (1e-12, 1e-12)
            result = MODULE.calculate('quad_parallel_capacitance', inputs)
            self.assertLess(result['window_margin'][0], 0)

    def test_both_derating_bounds_bind(self):
        for key, value in [('retained_lower_factor', (.4, .4)),
                           ('positive_upper_factor', (10, 10))]:
            inputs = fixture(4)
            inputs[key] = value
            self.assertLess(MODULE.calculate('quad_parallel_capacitance', inputs)['window_margin'][0], 0)

    def test_domains_and_shape(self):
        for key, value in [('capacitance_1', (0, 1)), ('required_window', (2, 1)),
                           ('retained_lower_factor', (1.1, 1.1)),
                           ('positive_upper_factor', (.9, .9))]:
            inputs = fixture(4)
            inputs[key] = value
            with self.assertRaises(ValueError):
                MODULE.calculate('quad_parallel_capacitance', inputs)
        with self.assertRaises(ValueError):
            MODULE.calculate('quad_parallel_capacitance', fixture(2))

    def test_immutable(self):
        inputs = fixture(4)
        original = dict(inputs)
        MODULE.calculate('quad_parallel_capacitance', inputs)
        self.assertEqual(inputs, original)


if __name__ == '__main__':
    unittest.main()
