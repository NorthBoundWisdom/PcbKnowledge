"""JSON queries and derived build output from validated workspaces or bundles."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import subprocess
from pathlib import Path

from pcbknowledge.git_native.workspace import validate_workspace
from pcbknowledge.serialization import canonical_json, read_json
from .bundle import Bundle, build_bundle
from .catalog import Catalog, MAX_RECORD_BYTES
from .coverage import coverage
from .expansion import expand_bundle
from .netlist import export_design


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--repo', type=Path, default=Path('.'))
    groups = result.add_subparsers(dest='group', required=True)
    v2 = groups.add_parser('v2').add_subparsers(dest='action', required=True)
    v2.add_parser('validate')
    check = v2.add_parser('coverage')
    check.add_argument('graph', type=Path)
    check.add_argument('--bundle', type=Path)
    footprint = groups.add_parser('footprint').add_subparsers(dest='action', required=True)
    footprint_export = footprint.add_parser('export')
    footprint_export.add_argument('--output', type=Path, default=Path('build/footprints/pcbknowledge.pretty'))
    footprint_export.add_argument('--bundle', type=Path)
    bundle = groups.add_parser('bundle').add_subparsers(dest='action', required=True)
    build = bundle.add_parser('build')
    build.add_argument('--output', type=Path, default=Path('build/bundle'))
    expand = groups.add_parser('expand')
    expand.add_argument('graph', type=Path)
    expand.add_argument('--bundle', type=Path, required=True)
    expand.add_argument('--output', type=Path)
    export = groups.add_parser('export')
    export.add_argument('--bundle', type=Path, required=True)
    export.add_argument('--graph', type=Path, required=True)
    export.add_argument('--intent', type=Path, required=True)
    export.add_argument('--output', type=Path, default=Path('build/design'))
    evaluation = groups.add_parser('eval-synthesis')
    evaluation.add_argument('--bundle', type=Path, required=True)
    evaluation.add_argument('--reference', type=Path, required=True)
    evaluation.add_argument('--attempt', type=Path, action='append', required=True)
    evaluation.add_argument('--output', type=Path)
    groups.add_parser('change-scope')
    for name in ('source', 'part', 'package', 'block', 'fab', 'registry'):
        actions = groups.add_parser(name).add_subparsers(dest='action', required=True)
        show = actions.add_parser('show')
        show.add_argument('id')
        show.add_argument('--bundle', type=Path)
        if name == 'source':
            authorize = actions.add_parser('authorize-read')
            authorize.add_argument('id')
        if name in ('part', 'block'):
            search = actions.add_parser('search')
            search.add_argument('--text', default='')
            search.add_argument('--bundle', type=Path)
            if name == 'part':
                search.add_argument('--role')
    return result


def derived_path(root, requested):
    """Resolve against the selected workspace and reject symlink/path escapes."""
    build = root / 'build'
    if build.resolve() != build:
        raise ValueError('Derived output build/ must not be a symlink')
    output = (requested if requested.is_absolute() else root / requested).resolve()
    if not output.is_relative_to(build) or output == build:
        raise ValueError('Derived output must be written below build/')
    return output


def load_document(path):
    if path.stat().st_size > MAX_RECORD_BYTES:
        raise ValueError('Oversized input document')
    document = read_json(path.read_bytes())
    if not isinstance(document, dict):
        raise ValueError('Input document must be a JSON object')
    return document


def change_scope(root):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args]).decode('utf-8').split('\0')
    paths = [p for p in git('diff', '--cached', '--name-only', '--no-renames', '-z') if p]
    if not paths:
        paths = [p for p in git('diff', '--name-only', '--no-renames', '-z')
                 + git('ls-files', '--others', '--exclude-standard', '-z') if p]
    data = any(p.startswith(('knowledge/', 'evidence/')) for p in paths)
    code = any(not p.startswith(('knowledge/', 'evidence/')) for p in paths)
    scope = 'MIXED' if data and code else 'DATA_ONLY' if data else 'CODE_ONLY' if code else 'CLEAN'
    return {'scope': scope, 'valid_for_single_commit': scope != 'MIXED'}


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        root = validate_workspace(arguments.repo).root.resolve()
        group = arguments.group
        with ExitStack() as stack:
            if group == 'change-scope':
                result = change_scope(root)
            elif group == 'bundle':
                path = build_bundle(root, derived_path(root, arguments.output))
                result = {'status': 'BUILT', 'bundle': str(path), 'commit': path.stem}
            elif group == 'expand':
                output = derived_path(root, arguments.output) if arguments.output else None
                result = expand_bundle(arguments.bundle, load_document(arguments.graph))
                if output:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text(canonical_json(result), encoding='utf-8', newline='\n')
            else:
                snapshot = (stack.enter_context(Bundle(arguments.bundle))
                            if getattr(arguments, 'bundle', None) else None)
                catalog = snapshot.catalog if snapshot else Catalog(root, root / 'schemas')
                if group == 'eval-synthesis':
                    from .synthesis import evaluate
                    result = evaluate(snapshot, load_document(arguments.reference),
                                      [load_document(path) for path in arguments.attempt])
                    if arguments.output:
                        output = derived_path(root, arguments.output)
                        output.parent.mkdir(parents=True, exist_ok=True)
                        output.write_text(canonical_json(result), encoding='utf-8', newline='\n')
                elif group == 'export':
                    output = derived_path(root, arguments.output)
                    path = export_design(load_document(arguments.intent), snapshot,
                                         load_document(arguments.graph), output)
                    result = {'status': 'EXPORTED', 'directory': str(path), 'commit': snapshot.commit}
                elif group == 'footprint':
                    from .footprints import export_library
                    files = export_library(catalog.search('package'), derived_path(root, arguments.output))
                    result = {'status': 'EXPORTED', 'files': [str(path) for path in files]}
                elif group == 'v2' and arguments.action == 'coverage':
                    result = coverage(catalog, load_document(arguments.graph))
                elif group == 'v2':
                    result = {'status': 'VALID', 'records': len(catalog.records), 'evidence': {
                        r['id']: catalog.evidence_status(r) for r in catalog.search('source')}}
                elif group == 'registry':
                    name = arguments.id.removeprefix('registry:')
                    if name not in catalog.vocabulary.entries:
                        raise ValueError('Unknown registry')
                    result = {'id': 'registry:' + name, 'entries': catalog.vocabulary.entries[name]}
                elif group == 'source' and arguments.action == 'authorize-read':
                    result = {'status': 'AUTHORIZED', 'source': arguments.id,
                              'path': str(catalog.authorize_read(arguments.id))}
                elif arguments.action == 'show':
                    result = catalog.get(arguments.id, 'fab_profile' if group == 'fab' else group)
                else:
                    result = catalog.search(group, arguments.text, getattr(arguments, 'role', None))
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
            if isinstance(result, dict) and (result.get('status') in ('REFUSED', 'INCOMPLETE', 'FAIL')
                                            or result.get('valid_for_single_commit') is False):
                return 2
            return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'ERROR', 'message': str(error)}, sort_keys=True))
        return 2
