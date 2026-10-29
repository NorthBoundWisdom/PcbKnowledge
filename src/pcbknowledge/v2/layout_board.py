"""Board-level measured handoff requirements, distinct from placement constraints."""
import math


def result(kind, state, reason, **measurements):
    return {'kind': kind, 'result': state, 'reason': reason, **measurements}


def limit(value, bound='value'):
    number = value.get(bound, value.get('value'))
    if value.get('unit') != 'mm' or isinstance(number, bool) or not isinstance(number, (int, float)):
        raise ValueError('Resolved millimetre limit required')
    if not math.isfinite(number) or number <= 0:
        raise ValueError('Finite positive millimetre limit required')
    return number


def envelope_check(board, intent):
    envelope = intent['mechanical']['outline_envelope']
    outline = board['outline']
    if envelope['shape'] != 'RECTANGLE' or not outline.get('closed') or not outline.get('rectangular'):
        return result('BOARD_ENVELOPE', 'NOT_CHECKABLE', 'Supported closed rectangular outline required')
    xmin, ymin, xmax, ymax = outline['bounds']
    width, length = xmax - xmin, ymax - ymin
    max_width = limit(envelope['max_width'], 'max')
    max_length = limit(envelope['max_length'], 'max')
    passed = 0 < width <= max_width + 0.000002 and 0 < length <= max_length + 0.000002
    return result('BOARD_ENVELOPE', 'PASS' if passed else 'FAIL',
                  'Actual outline width/length compared with intent envelope',
                  width_mm=width, length_mm=length, max_width_mm=max_width, max_length_mm=max_length)


def thickness_check(board, intent):
    expected = limit(intent['manufacturing']['thickness'])
    actual = board.get('thickness_mm')
    if actual is None:
        return result('BOARD_THICKNESS', 'NOT_CHECKABLE', 'Board has no declared thickness')
    passed = abs(actual - expected) <= 0.000002
    return result('BOARD_THICKNESS', 'PASS' if passed else 'FAIL',
                  'Declared board thickness compared with intent', thickness_mm=actual, expected_mm=expected)


def layers_check(board, intent):
    expected = intent['manufacturing']['layers']
    layers = board.get('copper_layers')
    if layers is None:
        return result('COPPER_LAYER_COUNT', 'NOT_CHECKABLE', 'Board has no enabled layer declaration')
    return result('COPPER_LAYER_COUNT', 'PASS' if len(layers) == expected else 'FAIL',
                  'Enabled copper layer count compared with intent', layers=layers, expected_count=expected)


def height_check(board, intent):
    height = intent['mechanical']['height_limit']
    if height.get('status') == 'UNCONSTRAINED':
        return result('COMPONENT_HEIGHT', 'PASS', 'Intent explicitly imposes no component height limit')
    return result('COMPONENT_HEIGHT', 'NOT_CHECKABLE',
                  'Board projection has no authoritative component 3D height evidence')


def assembly_check(board, intent):
    side = intent['manufacturing']['assembly_side']
    if side != 'TOP':
        return result('ASSEMBLY_SIDE', 'NOT_CHECKABLE', 'Unsupported or unresolved assembly side')
    if any('assembly_method' not in item for item in intent['components']):
        return result('ASSEMBLY_SIDE', 'NOT_CHECKABLE', 'Resolved component assembly metadata is required')
    misplaced = [item['ref'] for item in intent['components'] if item['assembly_method'] == 'SMT_ASSEMBLY'
                 and board['footprints'][item['ref']]['layer'] != 'F.Cu']
    return result('ASSEMBLY_SIDE', 'FAIL' if misplaced else 'PASS',
                  'Top-side assembly constraint applies to SMT_ASSEMBLY components', misplaced=misplaced)


def board_requirements(board, intent):
    checks = []
    handlers = [('BOARD_ENVELOPE', envelope_check), ('BOARD_THICKNESS', thickness_check),
                ('COPPER_LAYER_COUNT', layers_check), ('COMPONENT_HEIGHT', height_check),
                ('ASSEMBLY_SIDE', assembly_check)]
    for kind, handler in handlers:
        try:
            checks.append(handler(board, intent))
        except (KeyError, ValueError, TypeError) as error:
            checks.append(result(kind, 'NOT_CHECKABLE', 'Missing or unresolved board requirement: ' + str(error)))
    return checks
