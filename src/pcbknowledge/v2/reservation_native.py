"""Native read-only obstacle ranking for one authenticated failed-pad reservation."""
from pathlib import Path
from pcbknowledge.v2.fanout_solver import segments
from pcbknowledge.v2.fanout_native import propose, checked_hash
from pcbknowledge.v2.routing import input_fingerprints, unchanged_placement
from pcbknowledge.v2.sexpr import parse
from pcbknowledge.v2.boardview import children
from .reservation_core import copper_index, choose, digest


def _shapes(row):
    import pcbnew
    def vector(point):
        return pcbnew.VECTOR2I(round(point[0]*1e6), round(point[1]*1e6))
    lines = [pcbnew.SHAPE_SEGMENT(vector(a), vector(b), round(row['width']*1e6)) for a, b in segments(row)]
    via = pcbnew.SHAPE_CIRCLE(vector(row['end']), round(row['via_diameter']*5e5))
    hole = pcbnew.SHAPE_CIRCLE(vector(row['end']), round(row['via_drill']*5e5))
    layer = pcbnew.F_Cu if row['layer'] == 'F.Cu' else pcbnew.B_Cu
    return lines, via, hole, layer


def _blockers(native, index, row, rules):
    import pcbnew
    lines, via, drill, layer = _shapes(row)
    clearance = round(max(rules['clearance'], native.GetDesignSettings().m_MinClearance/1e6)*1e6)
    hole_clearance = round(max(rules['clearance'], native.GetDesignSettings().m_HoleClearance/1e6)*1e6)
    hole_to_hole = native.GetDesignSettings().m_HoleToHoleMin
    result = []
    for item in native.GetTracks():
        uid = item.m_Uuid.AsString()
        if uid not in index or item.IsLocked():
            raise ValueError('Native copper identity or lock mismatch')
        hit = False
        for copper in (pcbnew.F_Cu, pcbnew.B_Cu):
            if not item.IsOnLayer(copper):
                continue
            shape = item.GetEffectiveShape(copper)
            if item.GetNetname() != row['net']:
                hit |= shape.Collide(via, clearance)
                hit |= copper == layer and any(shape.Collide(line, clearance) for line in lines)
            hit |= shape.Collide(drill, hole_clearance)
        if item.HasDrilledHole():
            hole = item.GetEffectiveHoleShape()
            hit |= hole.Collide(via, hole_clearance)
            hit |= hole.Collide(drill, hole_to_hole)
            hit |= any(hole.Collide(line, hole_clearance) for line in lines)
        if hit:
            result.append({'uuid': uid, 'net': item.GetNetname(), 'node': index[uid]})
    return sorted(result, key=lambda row: row['uuid'])


def reservation(root, original, current, prior, drc, request, intent, catalog):
    """Generate a proposal only; native board emission is a separate reviewed action."""
    import pcbnew
    original, current, prior = map(Path, (original, current, prior))
    from .boardview import parse_board
    from .layout import identity_check
    if identity_check(parse_board(original), intent, catalog)['result'] != 'PASS':
        raise ValueError('Original physical board differs from validated intent')
    source_text, current_text = original.read_text(), current.read_text()
    prior_text = prior.read_text()
    source_hash, current_hash, prior_hash = map(digest, (source_text, current_text, prior_text))
    current_files = input_fingerprints(current)
    source_files = input_fingerprints(original)
    for suffix in ('.kicad_pro', '.kicad_dru'):
        if current_files[str(current.with_suffix(suffix))] != source_files[str(original.with_suffix(suffix))]:
            raise ValueError('Current settings differ from source authority')
    a, b = parse(current_text), parse(prior_text)
    for kind in ('segment', 'via', 'arc', 'footprint', 'net'):
        if children(a, kind) != children(b, kind):
            raise ValueError('Current pre-fill geometry differs from authenticated prior DRC')
    unchanged_placement(original, current)
    index = copper_index(a)
    base = propose(root, original, prior, drc, [request], intent, catalog,
                   placed_sha256=source_hash, prior_sha256=prior_hash)
    manager = pcbnew.GetSettingsManager()
    project_path = str(current.with_suffix('.kicad_pro'))
    if not manager.LoadProject(project_path):
        raise ValueError('Cannot load authenticated current project')
    native = pcbnew.LoadBoard(str(current))
    native.SetProject(manager.GetProject(project_path))
    settings = native.GetDesignSettings()
    actual_settings = {name: getattr(settings, name)/1e6 for name in
                       ('m_MinClearance', 'm_HoleClearance', 'm_HoleToHoleMin', 'm_CopperEdgeClearance')}
    if any(z.GetIsRuleArea() for z in native.Zones()):
        raise ValueError('Reservation keepout geometry unsupported')
    if any(z.GetFilledPolysList(l).OutlineCount() for z in native.Zones()
           for l in (pcbnew.F_Cu, pcbnew.B_Cu) if z.IsOnLayer(l)):
        raise ValueError('Reservation needs pre-fill copper')
    options = base['verified_candidates'][request['uuid']]
    rows = [{'candidate': row, 'blockers': _blockers(native, index, row, base['rules'])} for row in options]
    selection = choose(rows)
    checked_hash(original, source_hash)
    checked_hash(current, current_hash)
    checked_hash(prior, prior_hash)
    if input_fingerprints(current) != current_files or input_fingerprints(original) != source_files:
        raise ValueError('Reservation authority changed during proposal')
    return {'status': 'PROPOSAL', 'source_sha256': source_hash, 'current_sha256': current_hash,
            'prior_sha256': prior_hash, 'current_files_sha256': current_files,
            'source_files_sha256': source_files, 'request': request, 'rules': base['rules'],
            'candidate_statistics': base['candidate_statistics'], 'examined_candidates': len(rows),
            'selection': selection, 'native_settings_mm': actual_settings,
            'native_seed_drc': 'NOT_RUN', 'routing': 'NOT_RUN'}
