"""Deterministic KiCad rules derived from validated manufacturing and net inputs."""
import json


def millimeters(quantity, *, bound='value'):
    if quantity.get('unit') != 'mm' or quantity.get('status'):
        raise ValueError('Handoff requires concrete millimeters')
    value = quantity.get(bound, quantity.get('value'))
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError('Handoff requires a positive dimension')
    return value


def quote(value):
    return json.dumps(str(value), ensure_ascii=True)


def rule(name, constraint, minimum, condition=None):
    lines = [f'(rule {quote(name)}']
    if condition:
        lines.append(f'  (condition {quote(condition)})')
    lines.append(f'  (constraint {constraint} (min {minimum:.6f}mm)))')
    return '\n'.join(lines)


def differential_pairs(intent):
    nets = {net['name'] for net in intent['nets']}
    used = set()
    pairs = []
    for item in intent['layout']:
        if item['kind'] != 'DIFFERENTIAL_PAIR':
            continue
        pair = item['nets']
        if (not isinstance(pair, list) or len(pair) != 2 or len(set(pair)) != 2
                or not set(pair) <= nets or used.intersection(pair)):
            raise ValueError('Differential pair requires two unique, non-overlapping known nets')
        left, right = sorted(pair)
        if left[:-1] != right[:-1] or {left[-1:], right[-1:]} not in ({'+', '-'}, {'P', 'N'}):
            raise ValueError('KiCad differential net names require matching stems and P/N or +/- suffixes')
        used.update(pair)
        pairs.append({'nets': sorted(pair), 'width': millimeters(item['min_width']),
                      'gap': millimeters(item['gap']), 'skew': millimeters(item['max_skew'])})
    return sorted(pairs, key=lambda item: item['nets'])


def differential_rules(intent):
    lines = []
    for index, pair in enumerate(differential_pairs(intent), 1):
        escaped = [net.replace('\\', '\\\\').replace("'", "\\'") for net in pair['nets']]
        condition = ' || '.join("A.NetName == '" + net + "'" for net in escaped)
        prefix = f'(rule "differential-pair:{index}"\n  (condition {quote(condition)})\n'
        gap, skew = pair['gap'], pair['skew']
        lines.append(prefix + f'  (constraint diff_pair_gap (min {gap:.6f}mm) '
                     f'(opt {gap:.6f}mm) (max {gap:.6f}mm))\n'
                     f'  (constraint skew (max {skew:.6f}mm) (within_diff_pairs)))')
    return lines


def net_widths(intent, fab):
    widths = {net['name']: millimeters(fab['trace_width_min']) for net in intent['nets']}
    for item in intent['layout']:
        if item['kind'] == 'NET_WIDTH_MIN':
            widths[item['net']] = max(widths[item['net']], millimeters(item['min_width']))
    for pair in differential_pairs(intent):
        for net in pair['nets']:
            widths[net] = max(widths[net], pair['width'])
    return widths


def export_rules(intent, catalog):
    fab = catalog.get(intent['fab_profile'], 'fab_profile')
    lines = ['(version 1)']
    for key, constraint in (
        ('trace_width_min', 'track_width'), ('clearance_min', 'clearance'),
        ('drill_min', 'hole_size'), ('annular_ring_min', 'annular_width'),
    ):
        lines.append(rule('fab:' + key, constraint, millimeters(fab[key])))
    for net, width in sorted(net_widths(intent, fab).items()):
        # KiCad expressions use single quoted strings inside the rule string.
        escaped = net.replace('\\', '\\\\').replace("'", "\\'")
        lines.append(rule('net-width:' + net, 'track_width', width, f"A.NetName == '{escaped}'"))
    components = {item['ref']: item for item in intent['components']}
    mounting = {item['ref'] for item in intent['mechanical']['mounting']}
    for ref in sorted(mounting):
        offsets = [millimeters(item['distance']) for item in intent['layout']
                   if item['kind'] == 'EDGE_DISTANCE' and item['subject'] == ref]
        package = catalog.get(components[ref]['package'], 'package')
        from .footprints import derive_footprint
        pads = derive_footprint(package)['pads']
        radius = max(max(p.get('drill', 0), p.get('drill_width', 0), p.get('drill_height', 0)) for p in pads) / 2
        if not offsets or min(offsets) <= radius:
            raise ValueError('Mounting hole has no positive edge margin')
        escaped = ref.replace('\\', '\\\\').replace("'", "\\'")
        lines.append(rule('hole-edge:' + ref, 'edge_clearance', min(offsets) - radius,
                          f"A.Type == 'Pad' && A.FootprintReference == '{escaped}'"))
    lines.extend(differential_rules(intent))
    return '\n\n'.join(lines) + '\n'


def project_settings(intent, catalog):
    fab = catalog.get(intent['fab_profile'], 'fab_profile')
    clearance = millimeters(fab['clearance_min'])
    drill = millimeters(fab['drill_min'])
    ring = millimeters(fab['annular_ring_min'])
    widths = net_widths(intent, fab)
    classes = [{'name': 'Default', 'clearance': clearance, 'track_width': millimeters(fab['trace_width_min']),
                'via_diameter': drill + 2 * ring, 'via_drill': drill}]
    patterns = []
    for index, width in enumerate(sorted(set(widths.values())), 1):
        name = f'Width_{index}'
        classes.append({**classes[0], 'name': name, 'track_width': width})
        patterns.extend({'netclass': name, 'pattern': net} for net in sorted(widths) if widths[net] == width)
    for index, pair in enumerate(differential_pairs(intent), 1):
        name = f'Differential_{index}'
        width = max(widths[net] for net in pair['nets'])
        classes.append({**classes[0], 'name': name, 'track_width': width,
                        'diff_pair_width': width, 'diff_pair_gap': pair['gap']})
        patterns = [pattern for pattern in patterns if pattern['pattern'] not in pair['nets']]
        patterns.extend({'netclass': name, 'pattern': net} for net in pair['nets'])
    return {'meta': {'version': 1, 'filename': 'design.kicad_pro'},
            'net_settings': {'meta': {'version': 3}, 'classes': classes, 'netclass_patterns': patterns},
            'board': {'design_settings': {'rules': {'min_clearance': clearance,
                       'min_track_width': millimeters(fab['trace_width_min']),
                       'min_through_hole_diameter': drill, 'min_via_annular_width': ring}}}}
