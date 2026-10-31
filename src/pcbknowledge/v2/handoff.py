"""Derived unplaced KiCad project; no placement, routing or live-board mutation."""
import csv
from io import StringIO
from pathlib import Path
import uuid

from pcbknowledge.serialization import canonical_json
from .edge_constraints import validate_edge_constraints
from .footprints import derive_footprint, export_kicad
from .handoff_rules import export_rules, millimeters, project_settings
from .netlist import export_design


def _identity(intent, ref):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, intent['id'] + ':' + ref))


def _outline(intent):
    envelope = intent['mechanical']['outline_envelope']
    if envelope['shape'] != 'RECTANGLE':
        raise ValueError('Only rectangular outline envelopes are supported')
    return (millimeters(envelope['max_width'], bound='max'),
            millimeters(envelope['max_length'], bound='max'))


def _mount_positions(intent, width, height):
    positions = {}
    for mount in intent['mechanical']['mounting']:
        ref = mount['ref']
        axes = {}
        for item in intent['layout']:
            if item['kind'] != 'EDGE_DISTANCE' or item['subject'] != ref:
                continue
            distance = millimeters(item['distance'])
            edge = item['edge']
            axis = 'x' if edge in ('LEFT', 'RIGHT') else 'y'
            value = {'LEFT': distance, 'RIGHT': width - distance,
                     'TOP': distance, 'BOTTOM': height - distance}[edge]
            if axis in axes and axes[axis] != value:
                raise ValueError('Conflicting mounting edge distances')
            axes[axis] = value
        if set(axes) != {'x', 'y'} or not 0 < axes['x'] < width or not 0 < axes['y'] < height:
            raise ValueError('Mounting position requires two valid orthogonal edge distances')
        positions[ref] = (axes['x'], axes['y'])
    return positions


def _footprint(intent, component, catalog, position, connections):
    from .sexpr import parse
    package = catalog.get(component['package'], 'package')
    tree = parse(export_kicad(package))
    tree[1] = component['footprint']
    tree[:] = [item for item in tree if not isinstance(item, list) or item[0] not in ('version', 'generator')]
    tree.insert(2, ['at', *map(str, position)])
    tree.extend([['uuid', _identity(intent, component['ref'])],
                 ['property', 'Reference', component['ref'], ['at', '0', '0'], ['layer', 'F.Fab'],
                  ['effects', ['font', ['size', '1', '1'], ['thickness', '0.15']]]]])
    for node in tree:
        if isinstance(node, list) and node[0] == 'pad':
            key = component['ref'], node[1]
            if key in connections:
                code, name = connections[key]
                node.append(['net', str(code), name])
    return tree


def board_tree(intent, catalog):
    width, height = _outline(intent)
    validate_edge_constraints(intent['layout'], intent['mechanical']['outline_envelope'],
                              dimensions={'width': width, 'length': height})
    positions = _mount_positions(intent, width, height)
    nets = sorted(intent['nets'], key=lambda item: item['name'])
    connections = {(p['ref'], p['pin']): (i, net['name'])
                   for i, net in enumerate(nets, 1) for p in net['pins']}
    tree = ['kicad_pcb', ['version', '20241229'], ['generator', 'pcbknowledge'],
            ['general', ['thickness', str(millimeters(intent['manufacturing']['thickness']))]],
            ['paper', 'A4'], ['layers', ['0', 'F.Cu', 'signal'], ['31', 'B.Cu', 'signal'],
             ['34', 'B.Paste', 'user'], ['35', 'F.Paste', 'user'], ['36', 'B.SilkS', 'user'],
             ['37', 'F.SilkS', 'user'], ['38', 'B.Mask', 'user'], ['39', 'F.Mask', 'user'],
             ['44', 'Edge.Cuts', 'user'], ['46', 'B.CrtYd', 'user'], ['47', 'F.CrtYd', 'user'],
             ['48', 'B.Fab', 'user'], ['49', 'F.Fab', 'user']], ['setup', ['pad_to_mask_clearance', '0']],
            ['net', '0', '']]
    tree.extend(['net', str(i), net['name']] for i, net in enumerate(nets, 1))
    tree.append(['gr_rect', ['start', '0', '0'], ['end', str(width), str(height)],
                 ['stroke', ['width', '0.05'], ['type', 'default']], ['fill', 'none'], ['layer', 'Edge.Cuts']])
    cursor = 0.0
    for component in sorted(intent['components'], key=lambda item: item['ref']):
        package = catalog.get(component['package'], 'package')
        courtyard = derive_footprint(package)['courtyard']
        position = positions.get(component['ref'])
        if position is None:
            position = (width + 10 - courtyard['min_x'], cursor - courtyard['min_y'])
            cursor += courtyard['max_y'] - courtyard['min_y'] + 5
        tree.append(_footprint(intent, component, catalog, position, connections))
    return tree


def assembly_csv(intent, catalog):
    output = StringIO(newline='')
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(['references', 'mpn', 'manufacturer', 'footprint', 'mount_type', 'assembly_method', 'quantity'])
    components = {item['ref']: item for item in intent['components']}
    for item in sorted(intent['bom'], key=lambda item: item['part']):
        part = catalog.get(item['part'], 'part')
        footprints = {components[ref]['footprint'] for ref in item['refs']}
        if len(footprints) != 1:
            raise ValueError('BOM part has inconsistent footprint identities')
        writer.writerow([' '.join(sorted(item['refs'])), part['mpn'], part['manufacturer'], footprints.pop(),
                         item['mount_type'], item['assembly_method'], item['quantity']])
    return output.getvalue()


def _syntax(tree):
    from .sexpr import Atom
    import re
    result = []
    for index, item in enumerate(tree):
        if isinstance(item, list):
            result.append(_syntax(item))
        elif index == 0 or (isinstance(item, str) and (
                re.fullmatch(r'-?\d+(?:\.\d+)?', item)
                or item in {'signal', 'user', 'default', 'none', 'smd', 'through_hole', 'yes', 'edge'})):
            result.append(Atom(item))
        else:
            result.append(item)
    return result


def export_handoff(intent, bundle, graph, output):
    from .expansion import validate_expansion
    from .sexpr import dumps
    validate_expansion(bundle, intent, graph)
    if intent['status'] != 'EXPANDED':
        raise ValueError('Cannot export a refused design intent')
    payloads = {'design.kicad_pcb': dumps(_syntax(board_tree(intent, bundle.catalog))),
                'design.kicad_dru': export_rules(intent, bundle.catalog),
                'design.kicad_pro': canonical_json(project_settings(intent, bundle.catalog)),
                'assembly.csv': assembly_csv(intent, bundle.catalog),
                'fp-lib-table': '(fp_lib_table (version 7) (lib (name "pcbknowledge") (type "KiCad") '
                                '(uri "${KIPRJMOD}/pcbknowledge.pretty") (options "") (descr "")))\n'}
    output = Path(output)
    if any(path.is_symlink() for path in (output, *output.parents)):
        raise ValueError('Handoff output paths must not contain symlinks')
    for name in payloads:
        path = output / name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError('Unsafe handoff output target')
    export_design(intent, bundle, graph, output)
    for name, payload in payloads.items():
        (output / name).write_text(payload, encoding='utf-8', newline='\n')
    return output
