"""Translate unlocked KiCad DSN route state to Freerouting's actual unfixed token."""
import hashlib
from .boardview import children
from .sexpr import Atom, parse
from .specctra import read_specctra, write_specctra


def _source_locked_count(board_text):
    board = parse(board_text)
    if not board or board[0] != 'kicad_pcb':
        raise ValueError('Wire-state projection requires native source board')
    if children(board, 'group'):
        raise ValueError('Source copper group locking is unsupported')
    locked = 0
    for name in ('segment', 'arc', 'via'):
        for item in children(board, name):
            if any(not isinstance(value, list) and value == 'locked' for value in item[1:]):
                locked += 1
                continue
            fields = children(item, 'locked')
            if len(fields) > 1:
                raise ValueError('Duplicate native locked field')
            if fields:
                value = fields[0][1:]
                if value not in ([], ['yes'], ['no']):
                    raise ValueError('Unsupported native locked field')
                locked += value != ['no']
    return locked


def normalize_native_wire_states(dsn_text, board_text):
    """Only route→normal changes; existing protect/fix/shoveFixed are never weakened.

    Freerouting 2.5 treats KiCad's route token as USER_FIXED, not UNFIXED.
    Locked source copper makes this generic unlocked projection unsupported.
    """
    locked = _source_locked_count(board_text)
    if locked:
        raise ValueError('Cannot normalize source board containing locked copper')
    tree = read_specctra(dsn_text)
    if not tree or tree[0] != 'pcb':
        raise ValueError('Wire-state projection requires native DSN PCB')
    wiring = children(tree, 'wiring')
    if len(wiring) > 1:
        raise ValueError('Duplicate DSN wiring scope')
    counts = {
        'normalized_route': 0, 'already_normal': 0,
        'preserved_fixed': 0, 'implicit_unfixed': 0,
    }
    for scope in wiring:
        for item in children(scope, 'wire') + children(scope, 'via'):
            fields = children(item, 'type')
            if not fields:
                counts['implicit_unfixed'] += 1
                continue
            if len(fields) != 1 or len(fields[0]) != 2 or not isinstance(fields[0][1], Atom):
                raise ValueError('Malformed, quoted or duplicate DSN wire type')
            state = fields[0][1]
            if state == 'route':
                fields[0][1] = Atom('normal')
                counts['normalized_route'] += 1
            elif state == 'normal':
                counts['already_normal'] += 1
            elif state in ('protect', 'fix', 'shoveFixed', 'shove_fixed'):
                counts['preserved_fixed'] += 1
            else:
                raise ValueError('Unsupported DSN wire type: ' + state)
    output = write_specctra(tree)
    return output, {
        'status': 'PASS', **counts, 'source_locked_count': locked,
        'source_sha256': hashlib.sha256(board_text.encode()).hexdigest(),
        'dsn_input_sha256': hashlib.sha256(dsn_text.encode()).hexdigest(),
        'dsn_output_sha256': hashlib.sha256(output.encode()).hexdigest(),
    }
