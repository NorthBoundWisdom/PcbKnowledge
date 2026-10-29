"""Classify assembly work without treating through-hole items as refusals."""


def assembly_details(catalog, part, fab_id):
    package = catalog.get(part['package'], 'package')
    mount = package['mount_type']
    fab = catalog.get(fab_id, 'fab_profile')
    if mount == 'MECHANICAL':
        method = 'MECHANICAL'
    elif mount in fab['assembled_mount_types']:
        method = mount + '_ASSEMBLY'
    else:
        method = 'HAND_SOLDER'
    return {'mount_type': mount, 'assembly_method': method}


def attach_assembly(catalog, intent):
    for item in [*intent['components'], *intent['bom']]:
        part = catalog.get(item['part'], 'part')
        item.update(assembly_details(catalog, part, intent['fab_profile']))
    count = sum(item['mount_type'] == 'THT' for item in intent['components'])
    intent['checks'].append({
        'id': 'assembly:through-hole-count',
        'result': 'PASS',
        'reason': f'{count} through-hole components require THT assembly or hand soldering.',
    })


def validate_assembly(catalog, intent):
    for item in [*intent['components'], *intent['bom']]:
        part = catalog.get(item['part'], 'part')
        expected = assembly_details(catalog, part, intent['fab_profile'])
        if intent['status'] == 'REFUSED' and not any(key in item for key in expected):
            continue
        if any(item.get(key) != value for key, value in expected.items()):
            raise ValueError('Assembly metadata disagrees with package or selected fab service')
