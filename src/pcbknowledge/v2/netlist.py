"""Derived KiCad XML netlists and footprint libraries from validated intents."""
from pathlib import Path
from xml.etree import ElementTree as ET

from pcbknowledge.serialization import canonical_json
from .intent import validate_intent
from .footprints import export_library

KICAD_PIN_TYPES = {
    'POWER_IN': 'power_in', 'POWER_OUT': 'power_out', 'GROUND': 'power_in',
    'INPUT': 'input', 'OUTPUT': 'output', 'BIDIRECTIONAL': 'bidirectional',
    'OPEN_DRAIN': 'open_collector', 'ANALOG': 'unspecified',
    'PASSIVE': 'passive', 'NO_CONNECT': 'no_connect',
}


def export_netlist(intent, catalog, *, bundle_commit=None):
    validate_intent(catalog, intent, bundle_commit=bundle_commit or intent['bundle_commit'])
    if intent['status'] != 'EXPANDED':
        raise ValueError('Cannot export a refused design intent')
    root = ET.Element('export', version='D')
    design = ET.SubElement(root, 'design')
    ET.SubElement(design, 'source').text = intent['id']
    ET.SubElement(design, 'tool').text = 'PcbKnowledge v2'
    components = ET.SubElement(root, 'components')
    for component in sorted(intent['components'], key=lambda c:c['ref']):
        item = ET.SubElement(components, 'comp', ref=component['ref'])
        part = catalog.get(component['part'], 'part')
        ET.SubElement(item, 'value').text = part.get('mpn', part['id'])
        ET.SubElement(item, 'footprint').text = component['footprint']
        ET.SubElement(item, 'libsource', lib='pcbknowledge', part=part['id'])
        fields = ET.SubElement(item, 'fields')
        ET.SubElement(fields, 'field', name='PcbKnowledgePart').text = part['id']
    libparts = ET.SubElement(root, 'libparts')
    for identity in sorted({component['part'] for component in intent['components']}):
        part = catalog.get(identity, 'part')
        library_part = ET.SubElement(libparts, 'libpart', lib='pcbknowledge', part=identity)
        pins = ET.SubElement(library_part, 'pins')
        for pin in sorted(part['pins'], key=lambda p:p['number']):
            ET.SubElement(pins, 'pin', num=pin['number'], name=pin['name'], type=KICAD_PIN_TYPES[pin['type']])
    nets = ET.SubElement(root, 'nets')
    for code, net in enumerate(sorted(intent['nets'], key=lambda n:n['name']), 1):
        item = ET.SubElement(nets, 'net', code=str(code), name=net['name'])
        for pin in sorted(net['pins'], key=lambda p:(p['ref'],p['pin'])):
            ET.SubElement(item, 'node', ref=pin['ref'], pin=pin['pin'])
    ET.indent(root, space='  ')
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode') + '\n'


def export_design(intent, bundle, graph, output_dir):
    """All writes are derived output; no bundle or catalog authority is changed."""
    from .expansion import validate_expansion
    validate_expansion(bundle, intent, graph)
    payload = export_netlist(intent, bundle.catalog, bundle_commit=bundle.commit)
    output = Path(output_dir)
    for path in (output, *output.parents):
        if path.is_symlink():
            raise ValueError('Export paths must not contain symlinks')
    for name in ('design-intent.json','graph.json','design.net','pcbknowledge.pretty'):
        if (output / name).is_symlink():
            raise ValueError('Export targets must not be symlinks')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'design-intent.json').write_text(canonical_json(intent), encoding='utf-8', newline='\n')
    (output / 'design.net').write_text(payload, encoding='utf-8', newline='\n')
    (output / 'graph.json').write_text(canonical_json(graph), encoding='utf-8', newline='\n')
    identities = sorted({component['package'] for component in intent['components']})
    packages = [bundle.catalog.get(identity, 'package') for identity in identities]
    export_library(packages, output / 'pcbknowledge.pretty')
    return output
