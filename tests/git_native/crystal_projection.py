"""Exact D66 crystal migration and the already reviewed D54 G2 fuse correction."""
import copy

OLD_PART = 'part:abracon-abls-8-18'
NEW_PART = 'part:abracon-abmm2-8-18'
IDENTITIES = {
    OLD_PART: NEW_PART,
    'package:hc49-us-smd-abls': 'package:abracon-abmm2',
    'pcbknowledge:hc49-us-smd-abls': 'pcbknowledge:abracon-abmm2',
    'source:abracon-abls': 'source:abracon-abmm2',
}


def _one(test, rows):
    test.assertEqual(len(rows), 1)
    return rows[0]


def _part_contract(test, catalog):
    part = catalog.get(NEW_PART, 'part')
    test.assertEqual(part['mpn'], 'ABMM2-8.000MHZ-18-T')
    test.assertEqual(part['package'], 'package:abracon-abmm2')
    test.assertEqual(part['identity_evidence'], {'page': 2, 'source': 'source:abracon-abmm2'})
    test.assertEqual(part['pins'], [
        {'name': 'XTAL1', 'number': '1', 'type': 'PASSIVE'},
        {'name': 'GND', 'number': '2', 'type': 'GROUND'},
        {'name': 'XTAL2', 'number': '3', 'type': 'PASSIVE'},
        {'name': 'GND', 'number': '4', 'same_net_as': '2', 'type': 'GROUND'},
    ])
    test.assertEqual(part['pin_evidence']['source'], 'source:abracon-abmm2')
    test.assertEqual(part['pin_evidence']['page'], 3)


def _crystal(test, expected):
    component = _one(test, [c for c in expected['components'] if c['part'] == OLD_PART])
    ref = component['ref']
    for key in ('part', 'package', 'footprint'):
        test.assertIn(component[key], IDENTITIES)
        component[key] = IDENTITIES[component[key]]
    bom = _one(test, [row for row in expected['bom'] if row['part'] == OLD_PART])
    test.assertEqual(bom['refs'], [ref])
    test.assertEqual(bom['quantity'], 1)
    bom['part'] = NEW_PART
    signal = _one(test, [net for net in expected['nets'] if {'ref': ref, 'pin': '2'} in net['pins']])
    _one(test, [pin for pin in signal['pins'] if pin == {'ref': ref, 'pin': '2'}])['pin'] = '3'
    mcu = _one(test, [c for c in expected['components'] if c['part'] == 'part:st-stm32f103c8t6'])['ref']
    ground = _one(test, [net for net in expected['nets'] if {'ref': mcu, 'pin': '8'} in net['pins']])
    ground['pins'].extend({'ref': ref, 'pin': pin} for pin in ('2', '4'))
    ground['pins'].sort(key=lambda pin: (pin['ref'], pin['pin']))
    for item in expected['evidence']:
        if item['source'] == 'source:abracon-abls':
            item['source'] = 'source:abracon-abmm2'
    expected['dependencies'] = sorted(IDENTITIES.get(item, item) for item in expected['dependencies'])
    reasons = [('alias', '4', 'Aliased physical terminals share a net')]
    reasons += [('connection', pin, 'Required electrical pin connection') for pin in ('2', '4')]
    reasons += [('source', pin, 'Pin reaches a declared board power source') for pin in ('2', '4')]
    expected['checks'].extend({'id': f'{kind}:{ref}:{pin}', 'reason': reason, 'result': 'PASS'}
                              for kind, pin, reason in reasons)
    expected['checks'].sort(key=lambda check: check['id'])
    near = _one(test, [row for row in expected['layout'] if row['kind'] == 'PLACE_NEAR' and row['subject'] == ref])
    test.assertEqual(near['target'], mcu)
    test.assertEqual(near['max_distance']['value'], 5)
    near['target'] = mcu + '.pin:5'
    loop = _one(test, [row for row in expected['layout'] if row['kind'] == 'MINIMIZE_LOOP'
                      and ref + '.pin:2' in row['path']])
    test.assertEqual(loop['path'], [mcu + '.pin:5', ref + '.pin:1', ref + '.pin:2', mcu + '.pin:6'])
    test.assertEqual(loop['max_area']['value'], 25)
    loop['path'][2] = ref + '.pin:3'


def _d54_fuse(test, expected):
    fuse = _one(test, [c for c in expected['components'] if c['part'] == 'part:littelfuse-0451001-mrl'])['ref']
    rule = _one(test, [row for row in expected['layout']
                      if row['kind'] == 'EDGE_PLACEMENT' and row['subject'] == fuse])
    test.assertEqual(rule['edge'], 'LEFT')
    test.assertEqual(rule['max_distance']['value'], 8)
    rule['edge'] = 'RIGHT'
    rule['max_distance']['note'] = (
        'D54 aligns the input fuse with the adapter entry edge; D50 8 mm allowance retained.')
    net = _one(test, [net for net in expected['nets'] if {'ref': fuse, 'pin': '1'} in net['pins']])
    connector = _one(test, [pin for pin in net['pins'] if pin['ref'] != fuse])
    test.assertEqual(expected['layout'][-1]['kind'], 'NET_WIDTH_MIN')
    # Rule IDs order the D54 fuse rule before the existing final power-net rule.
    expected['layout'].insert(len(expected['layout']) - 1, {
        'kind': 'PLACE_NEAR', 'subject': fuse + '.pin:1',
        'target': connector['ref'] + '.pin:' + connector['pin'],
        'max_distance': {'basis': 'ENGINEERING_DEFAULT', 'conditions': {}, 'unit': 'mm', 'value': 5,
                         'note': 'D54 bounds the directly connected adapter connector pin to fuse pin distance.'},
    })
    expected['dependencies'].append('rule:fuse-connector-proximity')
    expected['dependencies'].sort()


def assert_reviewed_g2_projection(test, original, current, catalog):
    """Compare the complete intent after exactly the named reviewed changes; drop no fields."""
    _part_contract(test, catalog)
    test.assertEqual(len(original['checks']), 101)
    test.assertEqual(len(current['checks']), 106)
    expected = copy.deepcopy(original)
    _crystal(test, expected)
    _d54_fuse(test, expected)
    expected['bundle_commit'] = current['bundle_commit']
    test.assertEqual(expected, current)
