"""Run KiCad DRC on isolated copies of derived handoff files, never a live board."""
from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from pcbknowledge.serialization import canonical_json, read_json

MAX_BYTES = 32 * 1024 * 1024
from .drc_report_validation import REPORT_SCHEMA, aggregate_status, validate_drc_report, validate_native_report


def _derived(root, path):
    from .derived_paths import derived_output
    return derived_output(root, path)


def _inputs(root, board):
    board = Path(board)
    board = board if board.is_absolute() else Path(root).absolute() / board
    from .derived_paths import repository_boundary, repository_path
    within_repository = repository_boundary(root, board) is not None
    if within_repository:
        board = repository_path(root, board)
    if board.suffix != '.kicad_pcb':
        raise ValueError('DRC requires a derived .kicad_pcb board')
    files = [board, board.with_suffix('.kicad_pro'), board.with_suffix('.kicad_dru')]
    for path in files:
        if within_repository:
            repository_path(root, path)
        elif any(item.is_symlink() for item in (path, *path.parents)):
            raise ValueError('DRC input symlinks are forbidden')
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise ValueError('Missing or oversized DRC board/project/rules input')
    return files


def _library_inputs(board):
    """Only the generated local KiCad library may accompany the isolated project."""
    from .sexpr import parse

    table = board.parent / 'fp-lib-table'
    library = board.parent / 'pcbknowledge.pretty'
    if not table.exists() and not library.exists():
        return []
    if table.is_symlink() or library.is_symlink() or not table.is_file() or not library.is_dir():
        raise ValueError('Unsafe or incomplete derived footprint library')
    if table.stat().st_size > 65536:
        raise ValueError('Oversized footprint library table')
    tree = parse(table.read_text(encoding='utf-8'))
    if not tree or tree[0] != 'fp_lib_table':
        raise ValueError('Unsupported footprint library table')
    libraries = [item for item in tree[1:] if isinstance(item, list) and item and item[0] == 'lib']
    if not libraries:
        raise ValueError('Missing generated footprint library table entry')
    for entry in libraries:
        fields = {}
        for item in entry[1:]:
            if not isinstance(item, list) or not item or not isinstance(item[0], str) or item[0] in fields:
                raise ValueError('Malformed footprint library table field')
            fields[item[0]] = item[1:]
        if fields.get('uri') != ['${KIPRJMOD}/pcbknowledge.pretty'] or fields.get('type') != ['KiCad']:
            raise ValueError('Only the generated local footprint library is supported')
    files = sorted(library.iterdir())
    if len(files) > 512 or any(p.is_symlink() or not p.is_file() or p.suffix != '.kicad_mod' for p in files):
        raise ValueError('Unsafe or excessive footprint library files')
    if sum(p.stat().st_size for p in files) > MAX_BYTES:
        raise ValueError('Oversized footprint library')
    return [table, *files]


def _environment(directory):
    env = os.environ.copy()
    for name, relative in (
        ('HOME', 'home'), ('XDG_CONFIG_HOME', 'config'),
        ('XDG_CACHE_HOME', 'cache'), ('XDG_DATA_HOME', 'data'),
    ):
        path = directory / relative
        path.mkdir()
        env[name] = str(path)
    env['KICAD_CONFIG_HOME'] = str(directory / 'config')
    return env


def _parse_report(path):
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('Missing or oversized KiCad JSON report')
    report = read_json(path.read_bytes())
    validate_native_report(report)
    return report


def _invoke(executable, files, expected_digests):
    with tempfile.TemporaryDirectory(prefix='pcbknowledge-drc-') as name:
        directory = Path(name).resolve()
        env = _environment(directory)
        for path in files:
            relative = path.name
            if path.parent.name == 'pcbknowledge.pretty':
                relative = Path('pcbknowledge.pretty') / path.name
            destination = directory / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            key = path.relative_to(files[0].parent).as_posix()
            if hashlib.sha256(destination.read_bytes()).hexdigest() != expected_digests[key]:
                raise ValueError('Copied DRC input differs from recorded digest: ' + key)
        output = directory / 'drc-report.json'
        command = [executable, 'pcb', 'drc', '--format', 'json', '--severity-all',
                   '--exit-code-violations', '--output', str(output), str(directory / files[0].name)]
        process = subprocess.run(command, capture_output=True, text=True, timeout=120, env=env, cwd=directory)
        report = _parse_report(output)
        count = sum(len(report[key]) for key in ('violations', 'unconnected_items', 'schematic_parity'))
        return {
            'status': 'PASS' if process.returncode == 0 and count == 0 else 'FAIL',
            'exit_code': process.returncode, 'finding_count': count, 'report': report,
        }


def _write(root, path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    _derived(root, path)
    descriptor, name = tempfile.mkstemp(prefix='.drc-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(canonical_json(result))
        _derived(root, path)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run_drc(board, output, *, root, layout_report=None, kicad=None, schemas=None):
    """Return and save a bounded JSON receipt; missing KiCad never counts as passing A4."""
    from .report_contracts import validate_layout_report
    from .schema import ContractSchemas

    schemas = ContractSchemas() if schemas is None else schemas
    files = _inputs(root, board)
    files.extend(_library_inputs(files[0]))
    output = _derived(root, output)
    if output.suffix != '.json' or output in files or (
            output.exists() and any(output.samefile(path) for path in files)):
        raise ValueError('DRC output must be a separate derived JSON report')
    digests = {path.relative_to(files[0].parent).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in files}
    layout_report = copy.deepcopy(layout_report)
    if layout_report is not None:
        validate_layout_report(layout_report, schemas, board_sha256=digests[files[0].name])
    executable = shutil.which(str(kicad)) if kicad else shutil.which('kicad-cli')
    if not executable:
        result = {'status': 'NOT_RUN', 'reason': 'kicad-cli is unavailable'}
    else:
        try:
            result = _invoke(executable, files, digests)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            result = {'status': 'FAIL', 'reason': str(error)}
    drc_status = result['status']
    result.update(schema='pcbknowledge.drc.v2',
                  identity=copy.deepcopy(layout_report['identity']) if layout_report is not None else None,
                  layout_report=layout_report, board=str(files[0]), input_sha256=digests,
                  drc_status=drc_status, a4=drc_status,
                  status=aggregate_status(result, layout_report))
    validate_drc_report(result, schemas)
    _write(root, output, result)
    return result
