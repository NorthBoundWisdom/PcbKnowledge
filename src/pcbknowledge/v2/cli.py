"""JSON queries and derived build output from validated workspaces or bundles."""
from __future__ import annotations

import argparse
import hashlib
from contextlib import ExitStack
import json
import subprocess
from pathlib import Path

from pcbknowledge.workspace import validate_workspace
from pcbknowledge.serialization import canonical_json, read_json
from .audit import audit_catalog, require_audit
from .evidence import add_evidence, fetch_evidence
from .bundle import Bundle, build_bundle
from .catalog import Catalog, MAX_RECORD_BYTES
from .coverage import coverage, coverage_all
from .expansion import expand_bundle, validate_expansion
from .layout import check_board
from .handoff import export_handoff
from .drc import run_drc
from .netlist import export_design


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--repo', type=Path, default=Path('.'))
    groups = result.add_subparsers(dest='group', required=True)
    v2 = groups.add_parser('v2').add_subparsers(dest='action', required=True)
    v2.add_parser('validate')
    v2.add_parser('audit')
    evidence = groups.add_parser('evidence').add_subparsers(dest='action', required=True)
    fetch = evidence.add_parser('fetch')
    fetch.add_argument('--source')
    add = evidence.add_parser('add')
    add.add_argument('file', type=Path)
    check = v2.add_parser('coverage')
    check.add_argument('graph', type=Path, nargs='?')
    check.add_argument('--all', action='store_true')
    output_format = check.add_mutually_exclusive_group()
    output_format.add_argument('--json', action='store_true', help='Emit aggregate coverage JSON')
    output_format.add_argument('--human', action='store_true', help='Emit readable coverage lines')
    check.add_argument('--bundle', type=Path)
    footprint = groups.add_parser('footprint').add_subparsers(dest='action', required=True)
    footprint_export = footprint.add_parser('export')
    footprint_export.add_argument('--output', type=Path, default=Path('build/footprints/pcbknowledge.pretty'))
    footprint_export.add_argument('--bundle', type=Path)
    bundle = groups.add_parser('bundle').add_subparsers(dest='action', required=True)
    build = bundle.add_parser('build')
    build.add_argument('--output', type=Path, default=Path('build/bundle'))
    identity = bundle.add_parser('identity')
    identity.add_argument('--bundle', type=Path, required=True)
    capture = bundle.add_parser('snapshot')
    capture.add_argument('--bundle', type=Path, required=True)
    capture.add_argument('--brief', required=True)
    capture.add_argument('--skill', type=Path, required=True)
    capture.add_argument('--output', type=Path, required=True)
    expand = groups.add_parser('expand')
    expand.add_argument('graph', type=Path)
    expand.add_argument('--bundle', type=Path, required=True)
    expand.add_argument('--output', type=Path)
    export = groups.add_parser('export')
    export.add_argument('--bundle', type=Path, required=True)
    export.add_argument('--graph', type=Path, required=True)
    export.add_argument('--intent', type=Path, required=True)
    export.add_argument('--output', type=Path, default=Path('build/design'))
    bringup_parser(groups)
    synthesis_parser(groups)
    layout_parsers(groups)
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


def bringup_parser(groups):
    command = groups.add_parser('bringup', help='Emit an unobserved bring-up measurement plan')
    for name in ('bundle', 'graph', 'intent'):
        command.add_argument('--' + name, type=Path, required=True)
    command.add_argument('--output', type=Path, default=Path('build/bringup-report.json'))
    command.add_argument('--markdown', type=Path, help='Optional human checklist below build/')


def synthesis_parser(groups):
    evaluation = groups.add_parser('eval-synthesis')
    evaluation.add_argument('--bundle', type=Path, required=True)
    evaluation.add_argument('--reference', type=Path)
    evaluation.add_argument('--attempt', type=Path, action='append', required=True)
    evaluation.add_argument('--output', type=Path)
    evaluation.add_argument('--brief')
    evaluation.add_argument('--expected-refusal', type=Path, help='JSON object containing expected code and path')
    evaluation.add_argument('--orchestrator')
    evaluation.add_argument('--skill', type=Path)
    mode = evaluation.add_mutually_exclusive_group()
    mode.add_argument('--historical', action='store_true', help='Replay preserved commit-only corpus receipts')
    mode.add_argument('--replay', action='store_true', help='Replay prior v2 receipts with the current engine')


def layout_parsers(groups):
    actions = groups.add_parser('layout').add_subparsers(dest='action', required=True)
    export = actions.add_parser('export')
    export.add_argument('--bundle', type=Path, required=True)
    export.add_argument('--graph', type=Path, required=True)
    export.add_argument('--intent', type=Path, required=True)
    export.add_argument('--output', type=Path, default=Path('build/handoff'))
    check = actions.add_parser('check')
    check.add_argument('intent', type=Path)
    check.add_argument('board', type=Path)
    check.add_argument('--bundle', type=Path, required=True)
    check.add_argument('--graph', type=Path, required=True)
    check.add_argument('--output', type=Path, default=Path('build/layout-report.json'))
    drc = groups.add_parser('drc')
    drc.add_argument('board', type=Path)
    drc.add_argument('--output', type=Path, default=Path('build/drc-report.json'))
    for name in ('intent', 'bundle', 'graph'):
        drc.add_argument('--' + name, type=Path)


def derived_path(root, requested):
    from .derived_paths import derived_output
    return derived_output(root, requested)


def load_document(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Input document must be a regular non-symlink file')
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


def write_result(root, requested, result):
    if requested:
        output = derived_path(root, requested)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(canonical_json(result), encoding='utf-8', newline='\n')


def catalog_command(arguments, root, catalog, snapshot):
    group = arguments.group
    if group == 'bringup':
        return bringup_command(arguments, root, snapshot)
    if group == 'layout':
        return layout_command(arguments, root, snapshot)
    if group == 'eval-synthesis':
        return synthesis_command(arguments, root, snapshot)
    if group == 'export':
        output = derived_path(root, arguments.output)
        path = export_design(load_document(arguments.intent), snapshot, load_document(arguments.graph), output)
        return {'status': 'EXPORTED', 'directory': str(path), 'commit': snapshot.commit}
    if group == 'footprint':
        from .footprints import export_library
        files = export_library(catalog.search('package'), derived_path(root, arguments.output))
        return {'status': 'EXPORTED', 'files': [str(path) for path in files]}
    if group == 'v2':
        return validation_command(arguments, catalog)
    if group == 'evidence':
        if arguments.action == 'fetch':
            return fetch_evidence(catalog, arguments.source)
        return add_evidence(catalog, arguments.file)
    if group == 'registry':
        name = arguments.id.removeprefix('registry:')
        if name not in catalog.vocabulary.entries:
            raise ValueError('Unknown registry')
        return {'id': 'registry:' + name, 'entries': catalog.vocabulary.entries[name]}
    if group == 'source' and arguments.action == 'authorize-read':
        return {'status': 'AUTHORIZED', 'source': arguments.id, 'path': str(catalog.authorize_read(arguments.id))}
    if arguments.action == 'show':
        return catalog.get(arguments.id, 'fab_profile' if group == 'fab' else group)
    return catalog.search(group, arguments.text, getattr(arguments, 'role', None))


def same_file(first, second):
    return first == second or (first.exists() and second.exists() and first.samefile(second))


def protect_report_outputs(destinations, inputs):
    outputs = [path for path in destinations if path is not None]
    sources = [Path(path).resolve() for path in inputs if path is not None]
    for target in outputs:
        if target.exists() and target.stat().st_nlink > 1:
            raise ValueError('Report output must not overwrite a multiply linked file')
        if any(same_file(target, source) for source in sources):
            raise ValueError('Report output must not overwrite an input')
    if any(same_file(a, b) for index, a in enumerate(outputs) for b in outputs[index + 1:]):
        raise ValueError('Report destinations must differ')


def bringup_command(arguments, root, snapshot):
    from .bringup import make_bringup, render_bringup

    output = derived_path(root, arguments.output)
    markdown = derived_path(root, arguments.markdown) if arguments.markdown else None
    protect_report_outputs((output, markdown), (arguments.intent, arguments.graph, arguments.bundle))
    intent, graph = load_document(arguments.intent), load_document(arguments.graph)
    validate_expansion(snapshot, intent, graph)
    report = make_bringup(intent, graph, snapshot.briefs[graph['brief']], snapshot.catalog)
    checklist = render_bringup(report, schemas=snapshot.catalog.schemas) if markdown else None
    write_result(root, output, report)
    if markdown:
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(checklist, encoding='utf-8', newline='\n')
    return report


def synthesis_command(arguments, root, snapshot):
    from .synthesis import evaluate, evaluate_corpus, evaluate_historical_corpus, replay_corpus

    from .synthesis_evidence import load_attempt

    attempts = [load_attempt(root, path) for path in arguments.attempt]
    reference = load_document(arguments.reference) if arguments.reference else None
    if arguments.brief:
        if not arguments.orchestrator or not arguments.skill:
            raise ValueError('Corpus evaluation requires --orchestrator and --skill')
        skill = arguments.skill
        if skill.is_symlink() or not skill.is_file() or skill.stat().st_size > MAX_RECORD_BYTES:
            raise ValueError('Unsafe or oversized synthesis skill')
        expected = load_document(arguments.expected_refusal) if arguments.expected_refusal else None
        evaluator = (evaluate_historical_corpus if arguments.historical else
                     replay_corpus if arguments.replay else evaluate_corpus)
        result = evaluator(snapshot, arguments.brief, attempts, reference, expected,
                                 orchestrator=arguments.orchestrator, skill_text=skill.read_bytes().decode('utf-8'),
                                 bundle_sha256=hashlib.sha256(arguments.bundle.read_bytes()).hexdigest())
    else:
        if (reference is None or arguments.expected_refusal or arguments.orchestrator
                or arguments.skill or arguments.historical or arguments.replay):
            raise ValueError('Legacy synthesis needs --reference; corpus options require --brief')
        result = evaluate(snapshot, reference, attempts)
    write_result(root, arguments.output, result)
    return result


def corpus_coverage(catalog):
    return coverage_all(catalog)


def checked_layout(arguments, snapshot):
    intent = load_document(arguments.intent)
    graph = load_document(arguments.graph)
    validate_expansion(snapshot, intent, graph)
    result = check_board(arguments.board, intent, snapshot.catalog)
    return {**result, 'status': result['result']}


def layout_command(arguments, root, snapshot):
    output = derived_path(root, arguments.output)
    if arguments.action == 'export':
        path = export_handoff(load_document(arguments.intent), snapshot, load_document(arguments.graph), output)
        return {'status': 'EXPORTED', 'directory': str(path), 'commit': snapshot.commit}
    protect_report_outputs((output,), (arguments.board, arguments.intent, arguments.graph, arguments.bundle))
    result = checked_layout(arguments, snapshot)
    write_result(root, output, result)
    return result


def drc_command(arguments, root):
    context = [arguments.intent, arguments.bundle, arguments.graph]
    if any(context) and not all(context):
        raise ValueError('DRC layout context requires --intent, --bundle and --graph together')
    output = derived_path(root, arguments.output)
    protect_report_outputs((output,), (arguments.board, *context))
    report = None
    if all(context):
        with Bundle(arguments.bundle) as snapshot:
            report = checked_layout(arguments, snapshot)
            return run_drc(arguments.board, output, root=root, layout_report=report,
                           schemas=snapshot.catalog.schemas)
    return run_drc(arguments.board, output, root=root, layout_report=report)


def validation_command(arguments, catalog):
    if arguments.action == 'coverage':
        if arguments.all == bool(arguments.graph):
            raise ValueError('Coverage requires either a graph or --all, not both')
        if arguments.all:
            return corpus_coverage(catalog)
        return coverage(catalog, load_document(arguments.graph))
    if arguments.action == 'audit':
        return audit_catalog(catalog)
    audit = require_audit(catalog)
    return {
        'status': 'VALID', 'records': len(catalog.records), 'audit': audit,
        'evidence': {r['id']: catalog.evidence_status(r) for r in catalog.search('source')},
    }


def bundle_command(arguments, root):
    from .synthesis_identity import input_identity
    from .synthesis_inputs import capture_inputs

    if arguments.action == 'build':
        path = build_bundle(root, derived_path(root, arguments.output))
        return {'status': 'BUILT', 'bundle': str(path), 'commit': path.stem}
    if arguments.action == 'identity':
        with Bundle(arguments.bundle) as snapshot:
            return {'commit': snapshot.commit, 'input_identity': input_identity(snapshot)}
    output = derived_path(root, arguments.output)
    skill = arguments.skill
    if skill.is_symlink() or not skill.is_file() or skill.stat().st_size > MAX_RECORD_BYTES:
        raise ValueError('Unsafe or oversized synthesis skill')
    snapshot = capture_inputs(arguments.bundle, arguments.brief, skill.read_bytes().decode('utf-8'))
    write_result(root, output, snapshot)
    return {'status': 'CAPTURED', 'snapshot': str(output), 'input_identity': snapshot['input_identity']}


def dispatch(arguments, root):
    if arguments.group == 'drc':
        return drc_command(arguments, root)
    if arguments.group == 'change-scope':
        return change_scope(root)
    if arguments.group == 'bundle':
        return bundle_command(arguments, root)
    if arguments.group == 'expand':
        # Validate the destination before expansion, preserving no-work-on-unsafe-output behavior.
        output = derived_path(root, arguments.output) if arguments.output else None
        result = expand_bundle(arguments.bundle, load_document(arguments.graph))
        write_result(root, output, result)
        return result
    with ExitStack() as stack:
        snapshot = stack.enter_context(Bundle(arguments.bundle)) if getattr(arguments, 'bundle', None) else None
        catalog = snapshot.catalog if snapshot else Catalog(root, root / 'schemas')
        return catalog_command(arguments, root, catalog, snapshot)


def result_exit_code(result):
    if not isinstance(result, dict):
        return 0
    failures = {
        'REFUSED', 'INCOMPLETE', 'FAIL', 'FAILED', 'DIFFERENT_BYTES', 'INVALID', 'ERROR', 'NOT_CHECKABLE', 'NOT_RUN',
    }
    if result.get('status') in failures or result.get('valid_for_single_commit') is False:
        return 2
    return 0


def coverage_lines(result):
    """One compact line per brief; missing graphs never imply ready blocks."""
    lines = []
    for row in result['briefs']:
        blocks = (f"{row['blocks_ready']}/{row['blocks_total']}"
                  if row.get('graphs') else 'NOT_RUN')
        refusals = row['refusals'] + row['graph_refusals']
        reasons = ','.join(sorted({f"{item['code']}@{item['path']}" for item in refusals})) or 'none'
        lines.append(f"{row['brief']}: blocks ready={blocks}; screening={row['screening']}; "
                     f"graph={row['graph_readiness']}; refusals={reasons}")
    return '\n'.join(lines)


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        root = validate_workspace(arguments.repo).root.resolve()
        result = dispatch(arguments, root)
        if arguments.group == 'v2' and arguments.action == 'coverage' and arguments.all:
            if arguments.human:
                print(coverage_lines(result))
            elif arguments.json:
                print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
            else:
                for row in result['briefs']:
                    print(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False))
        else:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
        return result_exit_code(result)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'ERROR', 'message': str(error)}, sort_keys=True))
        return 2
