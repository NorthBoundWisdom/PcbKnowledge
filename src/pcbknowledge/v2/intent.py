"""Cross-reference checks for the ADR-023 design-intent handoff."""
from __future__ import annotations

from .catalog import LEVELS, unique


def validate_intent(catalog, intent, *, bundle_commit):
    catalog.structure(intent, 'design-intent.schema.json')
    if intent['bundle_commit'] != bundle_commit:
        raise ValueError('Design intent does not match selected bundle commit')
    catalog._anchors(intent)
    components = unique(intent['components'], 'ref', 'intent component ref')
    used = set()
    parts = {}
    for ref, component in components.items():
        part = catalog.get(component['part'], 'part')
        if component['package'] != part['package']:
            raise ValueError('Intent component package disagrees with selected part')
        if component['footprint'] != 'pcbknowledge:'+part['package'].split(':',1)[1]:
            raise ValueError('Footprint identity disagrees with selected package')
        parts[ref] = part
        used.update((part['id'], part['package']))
    nets = unique(intent['nets'], 'name', 'intent net name')
    connections = {}
    for name, net in nets.items():
        for endpoint in net['pins']:
            ref, number = endpoint['ref'], endpoint['pin']
            if ref not in parts or number not in {p['number'] for p in parts[ref]['pins']}:
                raise ValueError('Dangling design-intent pin')
            if (ref,number) in connections:
                raise ValueError('Intent pin connected more than once')
            connections[ref,number] = name
    bom = {}
    for item in intent['bom']:
        if item['part'] in bom or item['quantity'] != len(item['refs']):
            raise ValueError('Invalid BOM quantity or duplicate part')
        bom[item['part']] = set(item['refs'])
    expected = {}
    for ref, part in parts.items():
        expected.setdefault(part['id'],set()).add(ref)
    if bom != expected:
        raise ValueError('BOM does not cover the selected components exactly')
    for mount in intent['mechanical']['mounting']:
        if mount['ref'] not in components or 'mechanical.mounting-hole' not in parts[mount['ref']]['roles']:
            raise ValueError('Dangling mounting component')
    if not set(intent['mechanical']['edge_interfaces']) <= set(components):
        raise ValueError('Dangling edge-interface component')
    for constraint in intent['layout']:
        catalog._layout_references(constraint, {r:[p] for r,p in parts.items()}, set(nets))
    fab_id = intent['fab_profile']
    if isinstance(fab_id, str):
        fab = catalog.get(fab_id, 'fab_profile');used.add(fab_id)
        if intent['manufacturing']['layers'] != fab['layer_count']:
            raise ValueError('Manufacturing layer count differs from fab profile')
        if intent['manufacturing']['assembly_side'] != fab['assembly_side']:
            raise ValueError('Manufacturing assembly side differs from fab profile')
    checks = unique(intent['checks'], 'id', 'intent check id')
    if intent['status'] == 'EXPANDED':
        def concrete(value):
            if isinstance(value,dict):
                if value.get('status') == 'UNKNOWN':raise ValueError('Expanded intent uses UNKNOWN')
                for child in value.values():concrete(child)
            elif isinstance(value,list):
                for child in value:concrete(child)
        concrete(intent)
        required = set()
        for ref, part in parts.items():
            for pin in part['pins']:
                key = ref,pin['number']
                if pin['type'] in ('POWER_IN','GROUND','INPUT'):
                    if key not in connections:raise ValueError('Required electrical pin is unconnected')
                    required.add('connection:'+ref+':'+pin['number'])
                alias=pin.get('same_net_as')
                if alias and connections.get(key) != connections.get((ref,alias)):
                    raise ValueError('Aliased pins must share one net')
                if pin['type'] == 'POWER_IN':
                    required.add('decoupling:'+ref+':'+pin['number'])
                    rail = connections[key]
                    grounds = {connections[ref,p['number']] for p in part['pins']
                               if p['type']=='GROUND' and (ref,p['number']) in connections}
                    caps = [c for c,p in parts.items() if 'capacitor.ceramic' in p['roles']]
                    if not any(rail in {connections.get((c,p['number'])) for p in parts[c]['pins']}
                               and grounds & {connections.get((c,p['number'])) for p in parts[c]['pins']}
                               for c in caps):
                        raise ValueError('IC power pin has no connected decoupling capacitor')
        if not required <= checks.keys() or any(c['result'] != 'PASS' for c in checks.values()):
            raise ValueError('Electrical checks are incomplete or failed')
    def closure(identity):
        record=catalog.get(identity)
        if identity in visited:return
        visited.add(identity)
        if intent['status']=='EXPANDED':concrete(record)
        def anchors(value):
            if isinstance(value,dict):
                if 'source' in value and 'page' in value:closure(value['source'])
                for child in value.values():anchors(child)
            elif isinstance(value,list):
                for child in value:anchors(child)
        anchors(record)
        for override in record.get('overrides',[]):closure(override['rule'])
    used.update(anchor['source'] for anchor in intent['evidence'])
    visited=set()
    for identity in used:closure(identity)
    weakest=min((catalog.get(i)['verification'] for i in visited),key=LEVELS.index,default='DRAFT')
    if intent['verification'] != weakest:
        raise ValueError(f'Intent verification must be computed from all dependencies: {weakest}')
    return intent
