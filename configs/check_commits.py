#!/usr/bin/env python3
"""Check new commit subjects and separate knowledge changes from software."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TYPES = frozenset(('feat', 'fix', 'refactor', 'style', 'docs', 'test', 'chore',
                   'perf', 'ci', 'build', 'data'))
SUBJECT = re.compile(r'^\[([a-z]+)\]: \S(?:.*\S)?$')


def git(root, *arguments):
    return subprocess.check_output(['git', '-C', str(root), *arguments]).decode('utf-8')


def event_range(event, event_name):
    """Select only the introduced range, never recheck historical commits."""
    if event_name == 'pull_request':
        request = event['pull_request']
        return request['base']['sha'] + '..' + request['head']['sha']
    if event_name == 'push':
        before, after = event['before'], event['after']
        if set(after) == {'0'}:
            raise ValueError('A deleted branch has no commit range to validate')
        if set(before) == {'0'}:
            raise ValueError('A new branch push requires an explicit validated base..head range')
        return before + '..' + after
    if event_name == 'workflow_dispatch':
        return 'HEAD^..HEAD'
    raise ValueError('Unsupported CI event for commit validation')


def check(root, revision_range):
    if revision_range.startswith('-') or revision_range.count('..') != 1 or '...' in revision_range:
        raise ValueError('Expected an explicit base..head commit range')
    base, head = revision_range.split('..')
    if not base or not head or base.startswith('-') or head.startswith('-'):
        raise ValueError('Expected nonempty base and head revisions')
    for revision in (base, head):
        git(root, 'rev-parse', '--verify', revision + '^{commit}')
    commits = git(root, 'rev-list', '--reverse', revision_range, '--').splitlines()
    violations = []
    for commit in commits:
        subject = git(root, 'show', '-s', '--format=%s', commit).strip()
        match = SUBJECT.fullmatch(subject)
        if not match or match.group(1) not in TYPES:
            violations.append(f'{commit}: subject must be [type]: description')
            continue
        parents = git(root, 'rev-list', '--parents', '-n', '1', commit).split()[1:]
        if parents:
            changed = git(root, 'diff', '--name-only', '--no-renames', '-z', parents[0], commit, '--')
        else:
            changed = git(root, 'diff-tree', '--root', '--no-commit-id', '--name-only',
                          '--no-renames', '-r', '-z', commit)
        paths = [path for path in changed.split('\0') if path]
        data = any(path.startswith('knowledge/') for path in paths)
        software = any(not path.startswith('knowledge/') for path in paths)
        if data and software:
            violations.append(f'{commit}: MIXED knowledge and software changes')
        if match.group(1) == 'data' and (not data or software):
            violations.append(f'{commit}: [data] requires DATA_ONLY knowledge/ paths')
        elif match.group(1) != 'data' and data:
            violations.append(f'{commit}: only [data] may touch knowledge/')
    return commits, violations


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('range', nargs='?', default='origin/main..HEAD')
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--event', action='store_true', help='Use the GitHub Actions event range')
    args = parser.parse_args(argv)
    try:
        selected = args.range
        if args.event:
            payload = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))
            selected = event_range(payload, os.environ['GITHUB_EVENT_NAME'])
        commits, violations = check(args.repo, selected)
        for violation in violations:
            print(violation)
        print(f'[pcbknowledge] commit guard: {len(commits)} commits, {len(violations)} violations ({selected})')
        return 1 if violations else 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f'[pcbknowledge] commit guard failed: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
