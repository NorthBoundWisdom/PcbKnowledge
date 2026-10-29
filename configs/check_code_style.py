#!/usr/bin/env python3
"""Check readable standard-library Python source without third-party formatters."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = Path('configs/code_style_allowlist.json')


def violation(path, rule, line, content):
    return {'path': path, 'rule': rule, 'line': line,
            'fingerprint': hashlib.sha256(content.encode('utf-8')).hexdigest()}


def inspect_source(source, path):
    lines = source.splitlines()
    findings = []
    for number, line in enumerate(lines, 1):
        if len(line) > 120:
            findings.append(violation(path, 'line-length', number, line))
    tree = ast.parse(source, filename=path)
    statements = Counter(node.lineno for node in ast.walk(tree) if isinstance(node, ast.stmt))
    inline_lines = {line for line, count in statements.items() if count > 1}
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and lines[node.lineno - 1][:node.col_offset].strip():
            inline_lines.add(node.lineno)
    for node in ast.walk(tree):
        for attribute in ('body', 'orelse', 'finalbody'):
            body = getattr(node, attribute, None)
            if isinstance(body, list) and body and isinstance(body[0], ast.stmt):
                if getattr(node, 'lineno', None) == body[0].lineno:
                    inline_lines.add(body[0].lineno)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = min([node.lineno] + [item.lineno for item in node.decorator_list])
            if node.end_lineno - start + 1 > 80:
                content = '\n'.join(lines[start - 1:node.end_lineno])
                findings.append(violation(path, 'function-length', start, content))
    for number in sorted(inline_lines):
        findings.append(violation(path, 'multiple-statements', number, lines[number - 1]))
    return findings


def key(item):
    return item['path'], item['rule'], item['fingerprint']


def check(root, allowlist):
    findings = []
    source_root = root / 'src/pcbknowledge'
    if not source_root.is_dir() or source_root.is_symlink():
        raise ValueError('A regular src/pcbknowledge directory is required')
    for path in sorted(source_root.rglob('*.py')):
        if path.is_symlink():
            raise ValueError(f'Source symlinks are forbidden: {path}')
        findings.extend(inspect_source(path.read_text(encoding='utf-8'), path.relative_to(root).as_posix()))
    document = json.loads(allowlist.read_text(encoding='utf-8'))
    if set(document) != {'temporary_until', 'entries'} or document['temporary_until'] != 'Stage 6c':
        raise ValueError('Invalid explicit style allowlist')
    allowed = Counter()
    for entry in document['entries']:
        if set(entry) != {'path', 'rule', 'fingerprint', 'count'} or type(entry['count']) is not int:
            raise ValueError('Malformed style allowlist entry')
        if entry['count'] < 1 or key(entry) in allowed:
            raise ValueError('Duplicate or invalid style allowance')
        allowed[key(entry)] = entry['count']
    new = []
    for item in findings:
        identity = key(item)
        if allowed[identity]:
            allowed[identity] -= 1
        else:
            new.append(item)
    return findings, new


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--allowlist', type=Path)
    args = parser.parse_args(argv)
    try:
        total, findings = check(args.repo, args.allowlist or args.repo / ALLOWLIST)
        for item in findings:
            print(f"{item['path']}:{item['line']}: {item['rule']}")
        print(f'[pcbknowledge] style guard: {len(findings)} new violations; {len(total) - len(findings)} explicit allowances')
        return 1 if findings else 0
    except (OSError, ValueError, SyntaxError, KeyError, TypeError) as error:
        print(f'[pcbknowledge] style guard failed: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
