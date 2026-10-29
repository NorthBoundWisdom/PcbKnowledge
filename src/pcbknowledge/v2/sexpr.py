"""Small bounded reader for original KiCad S-expression projections."""
import json
import re

MAX_BYTES = 16 * 1024 * 1024
MAX_NODES = 500_000
MAX_DEPTH = 128
TOKEN = re.compile(r'\s+|;[^\n]*|[()]|"(?:\\.|[^"\\])*"|[^\s();"]+')


class Atom(str):
    """An unquoted source atom, distinct from a quoted string."""


def parse(text):
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Oversized or invalid S-expression input')
    stack = []
    result = None
    position = 0
    count = 0
    for match in TOKEN.finditer(text):
        if match.start() != position:
            raise ValueError('Malformed S-expression token')
        position = match.end()
        token = match.group()
        if token.isspace() or token.startswith(';'):
            continue
        count += 1
        if count > MAX_NODES:
            raise ValueError('Too many S-expression nodes')
        if token == '(':
            node = []
            if stack:
                stack[-1].append(node)
            elif result is not None:
                raise ValueError('Multiple S-expression roots')
            else:
                result = node
            stack.append(node)
            if len(stack) > MAX_DEPTH:
                raise ValueError('S-expression nesting exceeds limit')
        elif token == ')':
            if not stack:
                raise ValueError('Unmatched S-expression close')
            stack.pop()
        else:
            if not stack:
                raise ValueError('S-expression atom outside root')
            if token.startswith('"'):
                try:
                    token = json.loads(token)
                except ValueError as error:
                    raise ValueError('Invalid quoted S-expression atom') from error
            else:
                token = Atom(token)
            stack[-1].append(token)
    if position != len(text) or stack or result is None:
        raise ValueError('Incomplete S-expression')
    return result


def dumps(node):
    """Serialize lists and atoms; quoted strings preserve all special characters."""
    if isinstance(node, Atom):
        return str(node)
    if isinstance(node, list):
        return '(' + ' '.join(dumps(child) for child in node) + ')'
    if isinstance(node, (int, float)):
        return json.dumps(node, allow_nan=False)
    if not isinstance(node, str):
        raise ValueError('Unsupported S-expression atom')
    return json.dumps(node, ensure_ascii=False)
