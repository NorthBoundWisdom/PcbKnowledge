#!/usr/bin/env python3
"""Eval-only original geometry vectors and a separate authenticated consumer replay."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile

SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT / 'src'))
from pcbknowledge.serialization import canonical_json, read_json
from pcbknowledge.workspace import validate_workspace, WorkspaceError
from pcbknowledge.v2.boardview import parse_board
from pcbknowledge.v2.bundle import Bundle
from pcbknowledge.v2.cli import protect_report_outputs
from pcbknowledge.v2.derived_paths import derived_output, repository_path
from pcbknowledge.v2.layout import LayoutChecks
from pcbknowledge.v2.layout_conductor_keepout import check_conductor_keepout
from pcbknowledge.v2.layout_guard import check_guard_ring
from pcbknowledge.v2.layout_identity import authoritative_bounds
from pcbknowledge.v2.layout_kelvin import check_kelvin_geometry
from pcbknowledge.v2.layout_return import check_return_path
from pcbknowledge.v2.report_contracts import validate_layout_report
from pcbknowledge.v2.schema import ContractSchemas

STATES = {'PASS', 'FAIL', 'NOT_CHECKABLE'}
MAX_BYTES = 4 * 1024 * 1024


def fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or set(value) - set(required) - set(optional):
        raise ValueError('Wrong conformance fields: ' + ', '.join(required))


def text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 1024:
        raise ValueError('Expected nonempty bounded conformance text')


def relative_file(root, value):
    text(value)
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix() or any(p in ('.', '..') for p in path.parts) or '\\' in value:
        raise ValueError('Conformance requires canonical repository-relative paths')
    result = repository_path(root, value)
    if not result.is_file() or result.stat().st_size > MAX_BYTES:
        raise ValueError('Missing or oversized conformance input')
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashed_file(root, declaration, suffix):
    fields(declaration, ('path', 'sha256'))
    if not isinstance(declaration['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', declaration['sha256']):
        raise ValueError('Malformed conformance SHA-256')
    path = relative_file(root, declaration['path'])
    if path.suffix != suffix or digest(path) != declaration['sha256']:
        raise ValueError('Conformance input hash or suffix mismatch')
    return path


def _context_geometry(context):
    for name, geometry in context['derived_footprints'].items():
        text(name)
        fields(geometry, ('courtyard',))
        box = geometry['courtyard']
        fields(box, ('min_x', 'min_y', 'max_x', 'max_y'))
        if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1000000 for v in box.values()):
            raise ValueError('Malformed synthetic courtyard dimensions')
        if box['min_x'] >= box['max_x'] or box['min_y'] >= box['max_y']:
            raise ValueError('Unordered synthetic courtyard')
    for reference, name in context['footprint_geometry'].items():
        text(reference)
        if not isinstance(name, str) or name not in context['derived_footprints']:
            raise ValueError('Unresolved synthetic footprint geometry')


def validate_context(context, pin_types):
    fields(context, ('schema', 'scope', 'verification', 'production_bundle_eligible', 'description',
                     'derived_footprints', 'footprint_geometry', 'terminal_types', 'synthetic_evidence_tokens'))
    if (context['schema'] != 'pcbknowledge.conformance-context.v1' or context['scope'] != 'ISOLATED_MEASUREMENT'
            or context['verification'] != 'DRAFT' or context['production_bundle_eligible'] is not False):
        raise ValueError('Synthetic context must remain DRAFT and ineligible for production bundles')
    text(context['description'])
    for key in ('derived_footprints', 'footprint_geometry', 'terminal_types', 'synthetic_evidence_tokens'):
        if not isinstance(context[key], dict) or not 1 <= len(context[key]) <= 256:
            raise ValueError('Malformed conformance context mapping')
    _context_geometry(context)
    for endpoint, role in context['terminal_types'].items():
        if not re.fullmatch(r'[A-Za-z0-9_]+\.pin:[A-Za-z0-9_]+', endpoint) or role not in pin_types:
            raise ValueError('Malformed synthetic terminal role')
    for source, note in context['synthetic_evidence_tokens'].items():
        if source != 'source:synthetic':
            raise ValueError('Unexpected synthetic evidence token')
        text(note)
    return context


def _case(case, kinds, schemas):
    fields(case, ('id', 'scope', 'verification', 'board', 'context', 'rules', 'expected'))
    text(case['id'])
    if case['scope'] != 'ISOLATED_MEASUREMENT' or case['verification'] != 'DRAFT':
        raise ValueError('Measurement vectors must stay isolated DRAFT fixtures')
    rules, expected = case['rules'], case['expected']
    if not isinstance(rules, list) or not 1 <= len(rules) <= 256 or not isinstance(expected, list):
        raise ValueError('Malformed conformance rule vectors')
    if len(rules) != len(expected):
        raise ValueError('Conformance expectation count differs from rules')
    seen = set()
    for rule, target in zip(rules, expected):
        fields(rule, ('id', 'input'))
        fields(target, ('rule_id', 'kind', 'result'), ('reason_code',))
        text(rule['id'])
        if rule['id'] in seen or target['rule_id'] != rule['id']:
            raise ValueError('Duplicate or reordered conformance rule')
        seen.add(rule['id'])
        shape = schemas.load('layout-constraint.schema.json')
        schemas.check(shape, 'layout-constraint.schema.json')
        schemas.apply(rule['input'], shape, 'layout-constraint.schema.json')
        if rule['input']['kind'] not in kinds or target['kind'] != rule['input']['kind']:
            raise ValueError('Unknown or mismatched conformance kind')
        if target['result'] not in STATES:
            raise ValueError('Unknown conformance expectation result')
        if 'reason_code' in target:
            text(target['reason_code'])


def load_manifest(root, path):
    root = validate_workspace(root).root
    manifest_path = relative_file(root, path)
    manifest = read_json(manifest_path.read_bytes())
    fields(manifest, ('schema', 'description', 'coverage_registry', 'measurement_cases',
                      'consumer_replay', 'expected_status_counts'))
    if manifest['schema'] != 'pcbknowledge.conformance-manifest.v1':
        raise ValueError('Unsupported conformance manifest version')
    text(manifest['description'])
    if manifest['coverage_registry'] != 'knowledge/registry/layout-constraints.json':
        raise ValueError('Conformance coverage uses the selected workspace registry')
    kinds = set(read_json(relative_file(root, manifest['coverage_registry']).read_bytes())['entries'])
    pin_types = set(read_json(relative_file(root, 'knowledge/registry/pin-types.json').read_bytes())['entries'])
    cases = manifest['measurement_cases']
    if not isinstance(cases, list) or not 1 <= len(cases) <= 256:
        raise ValueError('Malformed conformance cases')
    schemas = ContractSchemas(Path(root) / 'schemas')
    authority = [root / 'pcbknowledge.workspace.json', root / manifest['coverage_registry'],
                 root / 'knowledge/registry/pin-types.json', *sorted((root / 'schemas').glob('*.json'))]
    seen, coverage, counts = set(), set(), Counter()
    tracked = {path: digest(path) for path in [manifest_path, *authority]}
    for case in cases:
        _case(case, kinds, schemas)
        if case['id'] in seen:
            raise ValueError('Duplicate conformance case')
        seen.add(case['id'])
        board = hashed_file(root, case['board'], '.kicad_pcb')
        context = hashed_file(root, case['context'], '.json')
        validate_context(read_json(context.read_bytes()), pin_types)
        tracked.update({board: digest(board), context: digest(context)})
        coverage.update(row['input']['kind'] for row in case['rules'])
        counts.update(row['result'] for row in case['expected'])
    if coverage != kinds:
        raise ValueError('Conformance corpus must cover every registry constraint kind')
    fields(manifest['expected_status_counts'], STATES)
    if any(type(v) is not int or v < 0 for v in manifest['expected_status_counts'].values()):
        raise ValueError('Malformed expected measurement counts')
    if dict(counts) != manifest['expected_status_counts']:
        raise ValueError('Expected status totals disagree with fixture instances')
    replay = manifest['consumer_replay']
    fields(replay, ('scope', 'graph', 'expected_result'))
    if replay != {'scope': 'BUNDLE_REPLAY', 'graph': 'evals/golden-designs/g1.block-graph.json', 'expected_result': 'FAIL'}:
        raise ValueError('Consumer replay is the original parked G1 handoff negative control')
    return manifest, tracked


def measure(board, rule, context):
    kind = rule['kind']
    if kind == 'KELVIN':
        return check_kelvin_geometry(board, rule, context['terminal_types'])
    handlers = {'RETURN_PATH': check_return_path, 'GUARD_RING': check_guard_ring,
                'CONDUCTOR_KEEPOUT': check_conductor_keepout}
    if kind in handlers:
        return handlers[kind](board, rule)
    checker = LayoutChecks(board, {'components': []}, None)
    checker.authority_bounds = {
        ref: authoritative_bounds(board['footprints'][ref], context['derived_footprints'][name])
        for ref, name in context['footprint_geometry'].items() if ref in board['footprints']}
    return checker.check(rule)


def unchanged(tracked):
    if any(not path.is_file() or path.is_symlink() or digest(path) != expected for path, expected in tracked.items()):
        raise ValueError('Conformance input changed during evaluation')


def run_measurements(root, manifest):
    rows, counts, per_kind = [], Counter(), {}
    for case in manifest['measurement_cases']:
        board = parse_board(hashed_file(root, case['board'], '.kicad_pcb'))
        context = read_json(hashed_file(root, case['context'], '.json').read_bytes())
        for rule, expected in zip(case['rules'], case['expected']):
            finding = measure(board, rule['input'], context)
            matches = all(finding.get(key) == value for key, value in expected.items() if key != 'rule_id')
            rows.append({'case': case['id'], 'rule_id': rule['id'], 'expected': expected,
                         'finding': finding, 'matched': matches})
            counts[finding['result']] += 1
            per_kind.setdefault(finding['kind'], Counter())[finding['result']] += 1
    summary = {kind: {'check_count': sum(values.values()),
                      'status_counts': {state: values[state] for state in sorted(STATES)},
                      'not_checkable_fraction': values['NOT_CHECKABLE'] / sum(values.values())}
               for kind, values in sorted(per_kind.items())}
    return {'scope': 'ISOLATED_MEASUREMENT', 'total': len(rows), 'matched': sum(row['matched'] for row in rows),
            'status_counts': {state: counts[state] for state in sorted(STATES)}, 'per_kind': summary, 'instances': rows}


def _cli(root, arguments, expected_exit):
    command = [sys.executable, str(SOURCE_ROOT / 'configs/pcbknowledge_agent.py'), '--repo', str(root), *map(str, arguments)]
    process = subprocess.run(command, capture_output=True, text=True, cwd=root, timeout=120)
    if process.returncode != expected_exit:
        raise ValueError('Consumer CLI failed: ' + process.stderr + process.stdout[-1000:])


def consumer_replay(root, bundle, replay, directory):
    with Bundle(bundle) as snapshot:
        graph_path = relative_file(snapshot.catalog.root, replay['graph'])
        graph = directory / 'graph.json'
        graph.write_bytes(graph_path.read_bytes())
        intent, handoff, report = directory / 'intent.json', directory / 'handoff', directory / 'layout.json'
        _cli(root, ['expand', graph, '--bundle', bundle, '--output', intent], 0)
        _cli(root, ['layout', 'export', '--bundle', bundle, '--graph', graph, '--intent', intent, '--output', handoff], 0)
        board = handoff / 'design.kicad_pcb'
        _cli(root, ['layout', 'check', intent, board, '--bundle', bundle, '--graph', graph, '--output', report], 2)
        value = read_json(report.read_bytes())
        validate_layout_report(value, snapshot.catalog.schemas, intent=read_json(intent.read_bytes()), board_sha256=digest(board))
        return {'scope': 'BUNDLE_REPLAY', 'bundle_commit': snapshot.commit, 'expected_result': replay['expected_result'],
                'result': value['result'], 'matched': value['result'] == replay['expected_result'],
                'identity': value['identity'], 'report': value}


def software_identity():
    paths = [Path(__file__).resolve(), SOURCE_ROOT / 'configs/pcbknowledge_agent.py',
             *sorted((SOURCE_ROOT / 'src').rglob('*.py'))]
    sources = {path.relative_to(SOURCE_ROOT).as_posix(): digest(path) for path in paths}
    head = subprocess.check_output(['git', '-C', str(SOURCE_ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    return {'software_checkout_head': head,
            'software_sources_sha256': hashlib.sha256(canonical_json(sources).encode('utf-8')).hexdigest()}


def run(root, manifest_path, bundle, output):
    root = validate_workspace(root).root.resolve()
    output = derived_output(root, output)
    if output.suffix != '.json':
        raise ValueError('Conformance output must be derived JSON')
    bundle = Path(bundle).absolute()
    if bundle.is_symlink() or not bundle.is_file() or output == bundle:
        raise ValueError('Explicit regular caller bundle required; output must differ')
    manifest, tracked = load_manifest(root, manifest_path)
    inputs_sha256 = {path.relative_to(root).as_posix(): value for path, value in sorted(tracked.items())}
    bundle_sha256 = digest(bundle)
    tracked[bundle] = bundle_sha256
    protect_report_outputs((output,), tracked.keys())
    software = software_identity()
    measurements = run_measurements(root, manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='conformance-', dir=output.parent) as temporary:
        directory = Path(temporary)
        replay = consumer_replay(root, bundle, manifest['consumer_replay'], directory)
        unchanged(tracked)
        matched = measurements['matched'] == measurements['total'] and replay['matched']
        result = {'schema': 'pcbknowledge.conformance-result.v1', 'status': 'MATCH' if matched else 'MISMATCH',
                  'measurements': measurements, 'consumer_replay': replay,
                  'provenance': {'manifest': manifest_path, 'inputs_sha256': inputs_sha256,
                                 'bundle_sha256': bundle_sha256, **software}}
        pending = directory / 'result.json'
        pending.write_text(canonical_json(result), encoding='utf-8')
        derived_output(root, output)
        protect_report_outputs((output,), tracked.keys())
        os.replace(pending, output)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--manifest', default='evals/conformance/manifest.json')
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('build/conformance/report.json'))
    args = parser.parse_args(argv)
    try:
        result = run(args.repo, args.manifest, args.bundle, args.output)
        print(canonical_json(result), end='')
        return 0 if result['status'] == 'MATCH' else 2
    except (OSError, ValueError, KeyError, TypeError, WorkspaceError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
