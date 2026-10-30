"""Source-backed behavior for intentionally unconnected input pins."""
from copy import deepcopy


def validate_unconnected_states(catalog, part):
    for pin in part['pins']:
        default = pin.get('unconnected_state')
        if default is None:
            continue
        if pin['type'] != 'INPUT':
            raise ValueError('Unconnected state is supported only for INPUT pins')
        catalog.vocabulary.member('unconnected-states', default['state'])
        for evidence in default['evidence']:
            catalog._anchors(evidence)


def connection_check(ref, pin, connected):
    result = {'id': 'connection:' + ref + ':' + pin['number'],
              'result': 'PASS' if connected else 'FAIL', 'reason': 'Required electrical pin connection'}
    default = pin.get('unconnected_state')
    if not connected and pin['type'] == 'INPUT' and default is not None:
        result.update(result='PASS', reason='Source-backed unconnected input state',
                      unconnected_state=deepcopy(default))
    return result


def validate_default_checks(parts, nets, checks):
    connected = {(p['ref'], p['pin']) for net in nets for p in net['pins']}
    expected = {}
    for ref, part in parts.items():
        for pin in part['pins']:
            if pin['type'] == 'INPUT' and pin.get('unconnected_state'):
                check = connection_check(ref, pin, (ref, pin['number']) in connected)
                if 'unconnected_state' in check:
                    expected[check['id']] = check['unconnected_state']
    actual = {key: value['unconnected_state'] for key, value in checks.items() if 'unconnected_state' in value}
    if actual != expected:
        raise ValueError('Unconnected input state checks differ from source-backed pin defaults')
