"""Source-traceable package arithmetic and real catalog evidence recursion."""
import unittest
import copy
from pcbknowledge.v2.calculators import calculate as dispatch
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.schema import ContractSchemas

def calculate(inputs):
    return dispatch("geometry_affine", inputs)

def verify_quantity(quantity, evidence_resolver):
    catalog = object.__new__(Catalog)
    catalog.evidence = evidence_resolver
    catalog._anchors(quantity)

def ds(v, unit='mm'):
    return {'value': v, 'unit': unit, 'basis': 'DATASHEET', 'conditions': {},
            'evidence': {'source': 'source:synthetic', 'page': 1}}

def constant(v, unit='1'):
    return {'value': v, 'unit': unit, 'basis': 'ENGINEERING_DEFAULT', 'conditions': {},
            'note': 'Explicit mathematical coordinate convention.'}

def affine(offset, dimension, factor):
    return calculate({'offset': offset, 'dimension': dimension, 'factor': constant(factor)})['coordinate']

def scale(q, f):
    return affine(constant(0, 'mm'), q, f)

class GeometryTests(unittest.TestCase):

    def test_quantity_schema_accepts_nested_geometry_and_rejects_unregistered_name(self):
        schemas = ContractSchemas()
        name = "quantity.schema.json"
        schema = schemas.load(name)
        value = scale(affine(ds(4.8), ds(3.1), 1), .5)
        schemas.apply(value, schema, name)
        value["calculator"] = "invented_geometry"
        with self.assertRaises(ValueError):
            schemas.apply(value, schema, name)

    def test_t2_span(self):
        self.assertEqual(scale(affine(ds(4.8), ds(3.1), 1), 0.5)['value'], 3.95)

    def test_t8_signed_rows(self):
        for i in range(9):
            self.assertEqual(affine(affine(scale(ds(20), -0.5), ds(7.1), 1), ds(1.5), i)['value'],
                             round(-2.9 + 1.5 * i, 6))
        self.assertEqual(scale(ds(17.5), -0.5)['value'], -8.75)

    def test_t8_islands(self):
        pitch = affine(ds(0.7), ds(0.4), 1)
        for i in [-1, 0, 1]:
            self.assertEqual(affine(affine(scale(ds(18), -0.5), ds(9.96), 1), pitch, i)['value'],
                             round(0.96 + 1.1 * i, 6))
            self.assertEqual(affine(affine(scale(ds(20), 0.5), ds(6.7), -1), pitch, i)['value'],
                             round(3.3 + 1.1 * i, 6))

    def test_interval_signed(self):
        q = ds(0)
        q.pop('value')
        q.update(min=17.85, max=18.15)
        from fractions import Fraction
        r = scale(q, -0.5)
        self.assertLessEqual(Fraction(r['min']), Fraction('-9.075'))
        self.assertGreaterEqual(Fraction(r['max']), Fraction('-8.925'))

    def test_wrong_units_and_keys(self):
        for bad in [dict(offset=ds(0), dimension=ds(1, 'V'), factor=constant(1)),
                    dict(offset=ds(0), dimension=ds(1), factor=constant(1), ignored=ds(2))]:
            with self.assertRaises(ValueError):
                calculate(bad)

    def test_invalid_numbers(self):
        for v in [True, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                scale(ds(v), 1)

    def test_bounds_typ_only_or_inverted(self):
        for update in [{'typ': 1}, {'min': 2, 'max': 1}]:
            q = ds(1)
            q.pop('value')
            q.update(update)
            with self.assertRaises(ValueError):
                scale(q, 1)

    def test_engineering_dimension_not_authority(self):
        with self.assertRaises(ValueError):
            scale(constant(-10, 'mm'), 1)

    def test_missing_evidence(self):
        q = ds(1)
        q.pop('evidence')
        with self.assertRaises(ValueError):
            scale(q, 1)

    def test_tampered_nested_or_unrelated_calculator(self):
        q = scale(ds(20), -0.5)
        q['value'] = -9
        with self.assertRaises(ValueError):
            affine(q, ds(7.1), 1)
        q = scale(ds(20), -0.5)
        q['calculator'] = 'rc_time'
        with self.assertRaises(ValueError):
            affine(q, ds(7.1), 1)

    def test_false_value_and_dangling_source(self):
        q = scale(ds(17.5), 0.5)

        def resolver(e):
            if e != {'source': 'source:synthetic', 'page': 1}:
                raise ValueError('Dangling evidence')
        verify_quantity(q, resolver)
        bad = copy.deepcopy(q)
        bad['value'] = 9
        with self.assertRaises(ValueError):
            verify_quantity(bad, resolver)
        bad = copy.deepcopy(q)
        bad['inputs']['dimension']['evidence']['page'] = 2
        with self.assertRaises(ValueError):
            verify_quantity(bad, resolver)

    def test_overflow(self):
        with self.assertRaises(ValueError):
            scale(ds(1e+308), 1e+308)

    def test_depth_limit(self):
        q = ds(0)
        for _ in range(34):
            q = {'value': 0, 'unit': 'mm', 'basis': 'CALCULATED', 'conditions': {},
                 'calculator': 'geometry_affine', 'inputs': {'offset': constant(0, 'mm'), 'dimension': q, 'factor': constant(1)}}
        with self.assertRaises(ValueError):
            scale(q, 1)

    def test_outward_rounding_overflow(self):
        offset = ds(1e+292)
        offset.pop('value')
        offset.update(min=1e+292, max=1e+292)
        with self.assertRaises(ValueError):
            affine(offset, ds(1.7976931348623157e+308), 1)

    def test_scalar_nonzero_underflow(self):
        for sign in [-1, 1]:
            with self.assertRaises(ValueError):
                scale(ds(sign * 5e-324), 0.1)

    def test_interval_underflow_retains_enclosure(self):
        from fractions import Fraction
        dimension = ds(5e-324)
        dimension.pop('value')
        dimension.update(min=5e-324, max=5e-324)
        r = scale(dimension, 0.1)
        self.assertLessEqual(Fraction(r['min']), Fraction('5e-325'))
        self.assertGreaterEqual(Fraction(r['max']), Fraction('5e-325'))
if __name__ == '__main__':
    unittest.main()
