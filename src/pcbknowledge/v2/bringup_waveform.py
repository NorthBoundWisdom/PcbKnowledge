"""D91 TPS5430 PH engineering waveform protocol; no acquisition or measured pass."""
import math
from fractions import Fraction

# Shape and canonical units only. Engineering numerical decisions live in the graph;
# catalog part parameters supply source limits. No implicit numerical defaults apply.
FIELDS = {'input_voltage': ('V', ('min', 'max')),
 'high_offset': ('V', ('min', 'max')),
 'low_level': ('V', ('min', 'max')),
 'positive_peak_offset': ('V', ('max',)),
 'positive_peak': ('V', ('max',)),
 'negative_peak': ('V', ('min',)),
 'positive_excursion_threshold': ('V', ('min', 'max')),
 'negative_excursion_threshold': ('V', ('min', 'max')),
 'positive_excursion_duration': ('s', ('max',)),
 'negative_excursion_duration': ('s', ('max',)),
 'edge_time': ('s', ('max',)),
 'plateau_edge_exclusion': ('s', ('min', 'max')),
 'excursion_merge_gap': ('s', ('min', 'max')),
 'frequency': ('Hz', ('min', 'max')),
 'bandwidth': ('Hz', ('min',)),
 'sample_rate': ('Hz', ('min',)),
 'probe_capacitance': ('F', ('max',)),
 'probe_range': ('V', ('min', 'max')),
 'settling_time': ('s', ('min',)),
 'record_duration': ('s', ('min',)),
 'low_voltage_uncertainty': ('V', ('max',)),
 'high_voltage_uncertainty': ('V', ('max',)),
 'timing_uncertainty': ('s', ('max',)),
 'logic_load': ('A', ('min', 'max')),
 'peak_inductor_current': ('A', ('max',)),
 'ambient': ('degC', ('min', 'max'))}
SOURCE_FIELDS = (
    'switch_node_absolute_voltage', 'switch_node_transient_voltage',
    'switch_node_negative_transient_duration_limit', 'input_voltage', 'frequency',
)


def source_limits(row, intent, catalog):
    if catalog is None:
        raise ValueError('Waveform validation requires selected source catalog')
    ref = row['at'].partition('.pin:')[0]
    part = next(c['part'] for c in intent['components'] if c['ref'] == ref)
    parameters = catalog.get(part, 'part')['parameters']
    if not set(SOURCE_FIELDS) <= set(parameters):
        raise ValueError('Selected part lacks required waveform source limits')
    limits = {name: parameters[name] for name in SOURCE_FIELDS}
    for name, q in limits.items():
        if q.get('basis') != 'DATASHEET' or not q.get('evidence'):
            raise ValueError('Waveform source limit must resolve to cited part data: ' + name)
    return limits


def _quantities(value):
    for key, (unit, bounds) in FIELDS.items():
        q = value[key]
        if set(q) != {'basis', 'unit', *bounds} or q['unit'] != unit or q['basis'] != 'ENGINEERING_DEFAULT':
            raise ValueError('Waveform quantity fields/unit/basis: ' + key)
        for bound in bounds:
            if type(q[bound]) not in (int, float) or not math.isfinite(q[bound]):
                raise ValueError('Waveform requires finite numeric quantities')
        if q.get('min', -math.inf) > q.get('max', math.inf):
            raise ValueError('Waveform bounds are reversed')
        if unit not in ('V', 'degC') and any(q[b] <= 0 for b in bounds):
            raise ValueError('Acquisition quantities must be positive')
    for key in ('low_voltage_uncertainty', 'high_voltage_uncertainty'):
        if value[key]['max'] <= 0:
            raise ValueError('Voltage uncertainties must be positive')
    for key in ('positive_excursion_threshold', 'negative_excursion_threshold',
                'plateau_edge_exclusion', 'excursion_merge_gap'):
        if value[key]['min'] != value[key]['max']:
            raise ValueError('Protocol threshold requires one unambiguous value: ' + key)


def validate_waveform(row, intent, endpoint, catalog):
    value = row['waveform']
    required = {'protocol', 'basis', 'input_at', 'probe', 'processing', 'note'} | set(FIELDS)
    if set(value) != required or value['protocol'] != 'TPS5430_PH_D91' or value['basis'] != 'ENGINEERING_DEFAULT':
        raise ValueError('Incomplete or unsupported engineering waveform protocol')
    if (value['probe'] != 'ACTIVE_DIFFERENTIAL'
            or value['processing'] != 'RAW_NO_AVERAGING_NO_FILTER' or not value['note']):
        raise ValueError('Waveform requires explicit raw acquisition and probe')
    ref, _, pin = row['at'].partition('.pin:')
    part = next((c['part'] for c in intent['components'] if c['ref'] == ref), None)
    if (part != 'part:ti-tps5430dda' or pin != '8'
            or row.get('reference_at') != ref + '.pin:6' or value['input_at'] != ref + '.pin:7'):
        raise ValueError('TPS5430 waveform requires PH8, GND6 and synchronous VIN7 on the same device')
    if endpoint(value['input_at'], 'POWER') == endpoint(row['at'], 'POWER'):
        raise ValueError('Waveform input must not be shorted to PH')
    endpoint(row['reference_at'], 'GROUND')
    _quantities(value)
    limits = source_limits(row, intent, catalog)
    _source_bounds(value, limits)
    _acquisition(value)
    return limits


def _source_bounds(value, limits):
    steady = limits['switch_node_absolute_voltage']
    transient = limits['switch_node_transient_voltage']
    duration = _exact(value['negative_excursion_duration']['max']) + _exact(value['timing_uncertainty']['max'])
    if duration >= _exact(limits['switch_node_negative_transient_duration_limit']['value']):
        raise ValueError('Negative transient plus uncertainty exceeds strict source duration')
    if (value['low_level']['min'] < steady['min'] or value['negative_peak']['min'] < transient['min']
            or value['positive_peak']['max'] > steady['max']):
        raise ValueError('Waveform exceeds selected part PH absolute limits')
    if not steady['min'] <= value['negative_excursion_threshold']['min'] <= value['low_level']['min']:
        raise ValueError('Negative excursion threshold must detect all below-steady-limit samples')
    for field in ('input_voltage','frequency'):
        if value[field]['min'] < limits[field]['min'] or value[field]['max'] > limits[field]['max']:
            raise ValueError('Protocol outside selected part operating range')


def _acquisition(value):
    # D105 instrument floor resolves the nanosecond excursions in this protocol.
    if value['bandwidth']['min'] < 1e9 or value['sample_rate']['min'] < 5e9:
        raise ValueError('D105 waveform acquisition requires at least 1 GHz and 5 GS/s')
    uncertainty = _exact(value['timing_uncertainty']['max'])
    if (1 / _exact(value['sample_rate']['min']) > uncertainty
            or Fraction(35, 100) / _exact(value['bandwidth']['min']) > uncertainty):
        raise ValueError('Acquisition resolution cannot meet the declared timing uncertainty')
    peak = _exact(value['input_voltage']['max']) + _exact(value['positive_peak_offset']['max'])
    if _exact(value['positive_peak']['max']) < peak:
        raise ValueError('Absolute positive peak must contain the VIN-relative peak envelope')
    if _exact(value['sample_rate']['min']) < 5 * _exact(value['bandwidth']['min']):
        raise ValueError('Protocol sample rate must be at least five times acquisition bandwidth')
    if _exact(value['record_duration']['min']) * _exact(value['frequency']['min']) < 100:
        raise ValueError('Protocol requires at least 100 cycles')
    if (value['negative_peak']['min'] > value['low_level']['min']
            or value['positive_peak_offset']['max'] < value['high_offset']['max']):
        raise ValueError('Peak envelope must contain plateau envelope')
    if (value['probe_range']['min'] > value['negative_peak']['min']
            or value['probe_range']['max'] < value['positive_peak']['max']):
        raise ValueError('Probe range must contain the full absolute peak envelope')
    if value['positive_excursion_threshold']['min'] < value['high_offset']['max']:
        raise ValueError('Positive excursion threshold cannot overlap the high plateau envelope')
    if value['plateau_edge_exclusion']['min'] < value['edge_time']['max']:
        raise ValueError('Plateau exclusion must cover the allowed edge time')


def _exact(value):
    return Fraction(str(value))
