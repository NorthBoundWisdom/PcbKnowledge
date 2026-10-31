"""Optional external-process fanout adapter. Never import pcbnew at module load.

Outputs are proposals requiring source-authoritative native DRC before routing.
"""
import hashlib
import json
import math
import time
from pathlib import Path

from .fanout_solver import allocate, segments, bounded_candidates
from .fanout_anchors import attachment_points


def checked_requests(requests, index, failed_uuids):
    if not isinstance(requests, list) or not requests:
        raise ValueError('Explicit nonempty failed-pad requests required')
    result = []
    seen = set()
    for request in requests:
        if set(request) != {'uuid', 'reference', 'pad', 'net'}:
            raise ValueError('Malformed fanout request')
        uuid = request['uuid']
        if uuid in seen or uuid not in failed_uuids or uuid not in index:
            raise ValueError('Duplicate, unknown or nonfailed pad UUID')
        seen.add(uuid)
        if request != index[uuid]:
            raise ValueError('Requested UUID/reference/pad/net mismatch')
        result.append(dict(request))
    return sorted(result, key=lambda row: row['uuid'])


def checked_hash(path, expected):
    actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError('Fanout source fingerprint changed')
    return actual


def authority(intent, catalog):
    from pcbknowledge.v2.handoff_rules import millimeters, net_widths
    fab = catalog.get(intent['fab_profile'], 'fab_profile')
    if fab['layer_count'] != 2 or fab['via_types'] != ['THROUGH']:
        raise ValueError('Fanout supports two copper layers and through vias only')
    # Stronger net-specific clearances are deliberately applied globally, never weakened.
    clearances = [millimeters(fab['clearance_min'])]
    for rule in intent.get('layout', []) :
        if 'min_clearance' in rule:
            clearances.append(millimeters(rule['min_clearance']))
    drill = millimeters(fab['drill_min'])
    return {'widths': net_widths(intent, fab), 'clearance': max(clearances),
            'via_drill': drill, 'via_diameter': drill + 2 * millimeters(fab['annular_ring_min'])}


def native_pad_blocked(pad, net, lines, via, clearance, layer, copper_layers, hole_clearance=None):
    """Native-shape adapter; hole obstacles apply even when pad and track nets agree."""
    hole_clearance = max(clearance, hole_clearance if hole_clearance is not None else clearance)
    for copper in copper_layers:
        if pad.IsOnLayer(copper) and pad.GetEffectiveShape(copper).Collide(via, clearance):
            return True
    if pad.HasDrilledHole():
        hole = pad.GetEffectiveHoleShape()
        if hole.Collide(via, hole_clearance) or any(hole.Collide(line, hole_clearance) for line in lines):
            return True
    if pad.GetNetname() != net and pad.IsOnLayer(layer):
        return any(pad.GetEffectiveShape(layer).Collide(line, clearance) for line in lines)
    return False


def _requested_pads(native, prior_native, drc, requests):
    pads = [p for f in native.GetFootprints() for p in f.Pads()]
    prior_pads = [p for f in prior_native.GetFootprints() for p in f.Pads()]
    index = {}
    for p in prior_pads:
        uuid = p.m_Uuid.AsString()
        if uuid in index:
            raise ValueError('Duplicate native pad UUID')
        index[uuid] = dict(uuid=uuid, reference=p.GetParentFootprint().GetReference(),
                           pad=p.GetNumber(), net=p.GetNetname())
    failed = {item['uuid'] for finding in drc['report']['unconnected_items'] for item in finding['items']}
    requests = checked_requests(requests, index, failed)
    def identity(p):
        return (p.GetParentFootprint().GetReference(), p.GetNumber(), tuple(p.GetPosition()),
                tuple(p.GetSize()), p.GetOrientationDegrees(), p.GetShape(),
                p.GetNetname(), p.GetAttribute(), tuple(p.GetDrillSize()),
                p.GetDrillShape(), tuple(p.GetLayerSet().Seq()))
    padmap = {}
    for p in prior_pads:
        if p.m_Uuid.AsString() not in {row['uuid'] for row in requests}:
            continue
        matches = [original for original in pads if identity(original) == identity(p)]
        if len(matches) != 1:
            raise ValueError('Ambiguous prior-to-placed physical pad identity')
        padmap[p.m_Uuid.AsString()] = matches[0]
    return pads, requests, padmap


def _static_checker(native, pads, view, rules):
    import pcbnew
    clearance = rules['clearance']
    diameter, drill = rules['via_diameter'], rules['via_drill']
    if not all(math.isfinite(v) and v > 0 for v in (clearance, diameter, drill)) or drill >= diameter:
        raise ValueError('Invalid authoritative fanout dimensions')
    box = view['outline']['bounds']
    edge = max(clearance, native.GetDesignSettings().m_CopperEdgeClearance / 1e6)
    hole_clearance = max(clearance, native.GetDesignSettings().m_HoleClearance / 1e6)

    def inside(point, radius):
        return box[0] + edge + radius <= point[0] <= box[2] - edge - radius and \
               box[1] + edge + radius <= point[1] <= box[3] - edge - radius

    def vector(point):
        return pcbnew.VECTOR2I(round(point[0] * 1e6), round(point[1] * 1e6))

    def legal(row):
        lines = [pcbnew.SHAPE_SEGMENT(vector(a), vector(b), round(row['width'] * 1e6)) for a, b in segments(row)]
        via = pcbnew.SHAPE_CIRCLE(vector(row['end']), round(diameter * 5e5))
        if not inside(row['end'], diameter / 2):
            return False
        if any(not inside(p, row['width'] / 2) for a, b in segments(row) for p in (a, b)):
            return False
        layer = pcbnew.F_Cu if row['layer'] == 'F.Cu' else pcbnew.B_Cu
        return not any(native_pad_blocked(p, row['net'], lines, via, round(clearance * 1e6),
                                          layer, (pcbnew.F_Cu, pcbnew.B_Cu), round(hole_clearance * 1e6)) for p in pads)

    return legal


def _sample_paths(native, pad, request, rules, legal, start, budget):
    import pcbnew
    diameter, drill = rules['via_diameter'], rules['via_drill']
    layers = [l for l in (pcbnew.F_Cu, pcbnew.B_Cu) if pad.IsOnLayer(l)]
    if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or len(layers) != 1:
        raise ValueError('Requested fanout pad must be single-side SMT')
    width = rules['widths'][request['net']]
    if not isinstance(width, (int, float)) or isinstance(width, bool) or not math.isfinite(width) or width <= 0:
        raise ValueError('Invalid authoritative trace width')
    center = [pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6]
    options = []

    def approve(row):
        budget['evaluations'] += 1
        if budget['evaluations'] > 12000 or time.monotonic() > budget['deadline']:
            raise ValueError('Fanout candidate budget exhausted (12000 evaluations / 30 seconds per endpoint)')
        row['pad_center'] = center
        return legal(row)

    for direction in range(4):
        angle = math.radians(-pad.GetOrientationDegrees() + direction * 90)
        dx, dy = math.cos(angle), math.sin(angle)
        for length in (.5, .625, .75, .875, 1, 1.25, 1.5, 2, 3, 4):
            bend = [round(start[0] + dx * diameter * length, 6),
                    round(start[1] + dy * diameter * length, 6)]
            for lateral in (0, -.5, .5, -1, 1, -1.5, 1.5, -2, 2, -3, 3, -4, 4, -6, 6, -8, 8):
                for forward in ((0,) if lateral == 0 else (abs(lateral), 0)):
                    # Forward=abs(lateral) gives 45 degrees; forward=0 gives 90 degrees.
                    end = [round(bend[0] + diameter * (forward * dx - lateral * dy), 6),
                           round(bend[1] + diameter * (forward * dy + lateral * dx), 6)]
                    row = dict(net=request['net'], layer=native.GetLayerName(layers[0]), start=start,
                               bend=bend if lateral else None, end=end, width=width,
                               via_diameter=diameter, via_drill=drill)
                    if approve(row):
                        options.append(row)
    if not options:
        for direction in range(4):
            angle = math.radians(-pad.GetOrientationDegrees() + direction * 90)
            dx, dy = math.cos(angle), math.sin(angle)
            for length in (.5, .625, .75, .875, 1, 1.25, 1.5, 2, 3, 4):
                bend = [round(start[0] + dx * diameter * length, 6),
                        round(start[1] + dy * diameter * length, 6)]
                for halfstep in range(-16, 17):
                    if not halfstep:
                        continue
                    lateral = halfstep / 2
                    bend2 = [round(bend[0] - lateral * dy * diameter, 6),
                             round(bend[1] + lateral * dx * diameter, 6)]
                    sign = 1 if lateral > 0 else -1
                    for final in (.5, .75, .875, 1, 1.5, 2):
                        end = [round(bend2[0] + diameter * final * (dx - sign * dy), 6),
                               round(bend2[1] + diameter * final * (dy + sign * dx), 6)]
                        row = dict(net=request['net'], layer=native.GetLayerName(layers[0]), start=start,
                                   bend=bend, bend2=bend2, end=end, width=width,
                                   via_diameter=diameter, via_drill=drill)
                        if approve(row):
                            options.append(row)
    return options


def _options(native, pad, request, rules, legal):
    import pcbnew
    center = [pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6]
    shapes = {pcbnew.PAD_SHAPE_RECT: 'rect', pcbnew.PAD_SHAPE_CIRCLE: 'circle', pcbnew.PAD_SHAPE_OVAL: 'oval'}
    if pad.GetShape() not in shapes:
        raise ValueError('Unsupported strict-interior fanout attachment shape')
    starts = attachment_points(center, [v / 1e6 for v in pad.GetSize()],
                               pad.GetOrientationDegrees(), shapes[pad.GetShape()])
    layer = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
    budget = {'evaluations': 0, 'deadline': time.monotonic() + 30}
    options, tested = [], 0
    width = rules['widths'][request['net']]
    if not math.isfinite(width) or width <= 0:
        raise ValueError('Invalid authoritative width')
    clearance = max(rules['clearance'], native.GetDesignSettings().m_MinClearance / 1e6)
    for start in starts:
        tested += 1
        point = pcbnew.VECTOR2I(round(start[0]*1e6), round(start[1]*1e6))
        if not pad.GetEffectiveShape(layer).Collide(point, 0):
            raise ValueError('Off-center attachment is not native pad copper')
        disk = pcbnew.SHAPE_CIRCLE(point, round(width*5e5))
        others = [p for f in native.GetFootprints() for p in f.Pads()]
        if any(p.GetNetname() != request['net'] and p.IsOnLayer(layer)
               and p.GetEffectiveShape(layer).Collide(disk, round(clearance*1e6)) for p in others):
            continue
        options = _sample_paths(native, pad, request, rules, legal, start, budget)
        if options:
            break
    options, domain = bounded_candidates(options)
    for row in options:
        a, b = segments(row)[0]
        first = pcbnew.SHAPE_SEGMENT(pcbnew.VECTOR2I(round(a[0]*1e6), round(a[1]*1e6)),
                                    pcbnew.VECTOR2I(round(b[0]*1e6), round(b[1]*1e6)), round(width*1e6))
        if not pad.GetEffectiveShape(layer).Collide(first, 0):
            raise ValueError('Attachment trace is not connected to original native pad copper')
    return options, {**domain, 'evaluations': budget['evaluations'], 'evaluation_limit': 12000,
                     'seconds_limit': 30, 'attachment_points_tested': tested,
                     'attachment_points_available': len(starts), 'pad_center': center,
                     'native_track_pad_overlap_verified': bool(options)}


def propose(root, placed, prior_board, drc, requests, intent, catalog, *, placed_sha256, prior_sha256):
    """Read boards and return jointly checked candidates; does not write copper."""
    from pcbknowledge.v2.kicad_bridge import _path
    from pcbknowledge.v2.routing import unchanged_placement, input_fingerprints
    from pcbknowledge.v2.boardview import parse_board
    import pcbnew
    started = time.monotonic()
    rules = authority(intent, catalog)
    placed = _path(root, placed, exists=True)
    source_files = input_fingerprints(placed)
    prior_board = _path(root, prior_board, exists=True)
    checked_hash(placed, placed_sha256)
    checked_hash(prior_board, prior_sha256)
    if drc.get('input_sha256', {}).get(prior_board.name) != prior_sha256:
        raise ValueError('Prior DRC does not authenticate its board')
    if Path(drc.get('board', '')).resolve() != prior_board:
        raise ValueError('Prior DRC board path mismatch')
    for suffix in ('.kicad_pro', '.kicad_dru'):
        expected = source_files[str(placed.with_suffix(suffix))]
        if drc['input_sha256'].get(prior_board.with_suffix(suffix).name) != expected:
            raise ValueError('Prior DRC did not use source-authoritative project/rules')
    unchanged_placement(placed, prior_board)
    view = parse_board(placed)
    if view['unsupported'] or not view['outline']['rectangular']:
        raise ValueError('Fanout needs supported geometry and rectangular outline')
    project = _path(root, placed.with_suffix('.kicad_pro'), exists=True)
    if not pcbnew.GetSettingsManager().LoadProject(str(project)):
        raise ValueError('Cannot load source-authoritative project settings')
    native = pcbnew.LoadBoard(str(placed))
    if any(d.IsOnLayer(l) for d in native.GetDrawings() for l in (pcbnew.F_Cu, pcbnew.B_Cu)):
        raise ValueError('Copper graphics are unsupported fanout obstacles')
    if any(list(f.Zones()) for f in native.GetFootprints()):
        raise ValueError('Footprint zones/keepouts are unsupported fanout obstacles')
    if any(g.IsOnLayer(l) for f in native.GetFootprints() for g in f.GraphicalItems()
           for l in (pcbnew.F_Cu, pcbnew.B_Cu)):
        raise ValueError('Footprint copper graphics are unsupported fanout obstacles')
    if list(native.GetTracks()):
        raise ValueError('Fanout proposal needs original track-free placed board')
    if any(z.GetIsRuleArea() for z in native.Zones()):
        raise ValueError('Fanout keepout geometry is not supported')
    if any(z.GetFilledPolysList(layer).OutlineCount() for z in native.Zones()
           for layer in (pcbnew.F_Cu, pcbnew.B_Cu) if z.IsOnLayer(layer)):
        raise ValueError('Fanout requires unfilled original zone definitions')
    prior_native = pcbnew.LoadBoard(str(prior_board))
    pads, requests, padmap = _requested_pads(native, prior_native, drc, requests)
    legal = _static_checker(native, pads, view, rules)
    candidates, statistics = {}, {}
    for request in requests:
        pad = padmap[request['uuid']]
        candidates[request['uuid']], statistics[request['uuid']] = _options(native, pad, request, rules, legal)
    result = allocate(candidates, rules['clearance'])
    checked_hash(placed, placed_sha256)
    checked_hash(prior_board, prior_sha256)
    if input_fingerprints(placed) != source_files:
        raise ValueError('Fanout changed source board/project/rules')
    return {**result, 'verified_candidates': candidates, 'candidate_statistics': statistics,
            'source_files_sha256': source_files,
            'candidate_counts': {k: len(v) for k, v in candidates.items()},
            'source_sha256': placed_sha256, 'prior_board_sha256': prior_sha256,
            'requests': requests, 'rules': rules, 'status': 'PROPOSAL',
            'generation_seconds': round(time.monotonic() - started, 6),
            'native_seed_drc': 'NOT_RUN', 'routing': 'NOT_RUN'}
