"""Hand-calculated interval cases for the six G1 engineering calculators."""
import unittest
from pcbknowledge.v2.calculators import calculate, evaluate_check, CalculationError


def q(value, unit):
    return {'value': value, 'unit': unit, 'basis': 'ENGINEERING_DEFAULT',
            'conditions': {}, 'note': 'Synthetic test input.'}


class CalculatorTests(unittest.TestCase):
    def test_ldo_headroom_retains_negative_margin(self):
        inputs = dict(input_voltage=q(4.75,'V'),output_voltage=q(3.3,'V'),
                      dropout=q(1.2,'V'),input_current=q(.15,'A'),series_resistance=q(2,'ohm'))
        self.assertAlmostEqual(calculate('ldo_headroom',inputs)['headroom']['min'],-.05)
        check={'calculator':'ldo_headroom','inputs':inputs,
               'require':{'output':'headroom','operator':'GE','limit':q(0,'V')}}
        self.assertEqual(evaluate_check(check,{})['result'],'FAIL')

    def test_ldo_power_and_junction_temperature(self):
        inputs=dict(input_voltage=q(5,'V'),output_voltage=q(3.3,'V'),output_current=q(.15,'A'),
                    quiescent_current=q(.001,'A'),ambient=q(40,'degC'),thermal_resistance=q(100,'degC/W'))
        outputs=calculate('ldo_dissipation',inputs)
        self.assertAlmostEqual(outputs['power']['max'],.26)
        self.assertAlmostEqual(outputs['junction_temperature']['max'],66)

    def test_led_current_and_resistor_power(self):
        outputs=calculate('led_resistor',dict(supply=q(3.3,'V'),forward_voltage=q(2,'V'),resistance=q(1000,'ohm')))
        self.assertAlmostEqual(outputs['current']['max'],.0013)
        self.assertAlmostEqual(outputs['power']['max'],.00169)

    def test_i2c_limits_and_margin(self):
        inputs=dict(supply=q(3.3,'V'),low_voltage=q(.4,'V'),sink_current=q(.003,'A'),
                    capacitance=q(100e-12,'F'),rise_time=q(1e-6,'s'),resistance=q(4700,'ohm'))
        outputs=calculate('i2c_pullup',inputs)
        self.assertAlmostEqual(outputs['resistance_min']['min'],966.6666666667)
        self.assertAlmostEqual(outputs['rise_time']['max'],398.231e-9)
        self.assertGreater(outputs['margin']['min'],0)
        inputs['resistance']=q(20000,'ohm')
        self.assertLess(calculate('i2c_pullup',inputs)['margin']['min'],0)

    def test_shunt_current_power_limits(self):
        outputs=calculate('shunt_resistor',dict(current=q(.5,'A'),resistance=q(.1,'ohm'),
                          sense_limit=q(.32,'V'),power_rating=q(.25,'W')))
        self.assertAlmostEqual(outputs['voltage']['max'],.05)
        self.assertAlmostEqual(outputs['power']['max'],.025)
        self.assertAlmostEqual(outputs['power_margin']['min'],.225)

    def test_trace_width_named_external_equation(self):
        outputs=calculate('trace_width',dict(current=q(1,'A'),temperature_rise=q(10,'degC'),
                         copper_thickness=q(.035,'mm')))
        self.assertAlmostEqual(outputs['trace_width']['max'],.3003867,places=5)

    def test_missing_unknown_wrong_unit_nonfinite_and_invalid_domain_refuse(self):
        good=dict(supply=q(3.3,'V'),forward_voltage=q(2,'V'),resistance=q(1000,'ohm'))
        for bad in ({}, {**good,'resistance':{'status':'UNKNOWN'}},
                    {**good,'resistance':q(0,'ohm')}, {**good,'supply':q(3.3,'A')},
                    {**good,'supply':q(float('nan'),'V')},
                    {**good,'forward_voltage':{'typ':2,'unit':'V'}}):
            with self.subTest(bad=bad), self.assertRaises(CalculationError):
                calculate('led_resistor',bad)
        with self.assertRaises(CalculationError):calculate('invented',{})

    def test_guaranteed_intervals_propagate_worst_cases(self):
        supply={**q(3.3,'V')};supply.pop('value');supply.update(min=3,max=3.6)
        resistance={**q(1000,'ohm')};resistance.pop('value');resistance.update(min=990,max=1010)
        result=calculate('led_resistor',dict(supply=supply,forward_voltage=q(2,'V'),resistance=resistance))
        self.assertAlmostEqual(result['current']['min'],1/1010)
        self.assertAlmostEqual(result['current']['max'],1.6/990)

class OscillatorTests(unittest.TestCase):
    def test_source_bounded_startup_and_drive(self):
        from pcbknowledge.v2.calculators import calculate
        def q(value, unit):
            return {'value': value, 'unit': unit, 'conditions': {}, 'basis': 'ENGINEERING_DEFAULT', 'note': 'Test input.'}
        inputs = {'transconductance': q(.025,'S'), 'resistance': q(60,'ohm'),
                  'frequency': q(8e6,'Hz'), 'shunt_capacitance': q(7e-12,'F'),
                  'load_capacitance': q(18e-12,'F'), 'drive_current': q(.001,'A'),
                  'power_rating': q(.001,'W')}
        outputs = calculate('oscillator_startup',inputs)
        self.assertGreater(outputs['margin']['min'], 5)
        self.assertAlmostEqual(outputs['drive_power']['max'],.00006*(1+7/18)**2)
        self.assertAlmostEqual(outputs['drive_margin']['min'],.001-.00006*(1+7/18)**2)
        inputs['resistance']=q(400,'ohm');inputs['power_rating']=q(.0001,'W')
        self.assertLess(calculate('oscillator_startup',inputs)['drive_margin']['min'],0)

    def test_explicit_guaranteed_bound_projection(self):
        from pcbknowledge.v2.calculators import evaluate_check
        def q(value,unit):return {'value':value,'unit':unit}
        check={'calculator':'led_resistor','inputs':{'supply':q(3.3,'V'),'forward_voltage':q(0,'V'),
            'resistance':{'component':'R','parameter':'resistance','bound':'min'}},
            'require':{'output':'current','operator':'LE','limit':q(.004,'A')}}
        components={'R':{'parameters':{'resistance':{'min':990,'typ':1000,'max':1010,'unit':'ohm'}}}}
        self.assertEqual(evaluate_check(check,{},components)['result'],'PASS')
        check['inputs']['resistance']['bound']='typ'
        self.assertEqual(evaluate_check(check,{},components)['result'],'REFUSED')
