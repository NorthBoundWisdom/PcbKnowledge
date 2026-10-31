"""Structural and semantic checks for saved native DRC wrapper receipts."""
from pathlib import PurePosixPath, PureWindowsPath

REPORT_SCHEMA = 'https://schemas.kicad.org/drc.v1.json'
NATIVE_FIELDS = ('exit_code', 'finding_count', 'report')


def validate_native_report(report):
    if not isinstance(report, dict) or report.get('$schema') != REPORT_SCHEMA:
        raise ValueError('Unsupported KiCad DRC report schema')
    if not isinstance(report.get('kicad_version'), str):
        raise ValueError('Missing KiCad version in report')
    for key in ('violations', 'unconnected_items', 'schematic_parity'):
        values = report.get(key)
        if not isinstance(values, list):
            raise ValueError('Malformed KiCad DRC findings')
        if any(not isinstance(item, dict) or not isinstance(item.get('type'), str) for item in values):
            raise ValueError('Malformed KiCad DRC finding')
    return sum(len(report[key]) for key in ('violations', 'unconnected_items', 'schematic_parity'))


def aggregate_status(drc_result, layout_report):
    """Overall status combines native A4 DRC and validated measured layout."""
    layout_status = layout_report['result'] if layout_report is not None else None
    if drc_result['status'] == 'FAIL' or layout_status == 'FAIL':
        return 'FAIL'
    if drc_result['status'] == 'NOT_RUN':
        return 'NOT_RUN'
    if layout_status != 'PASS':
        return 'NOT_CHECKABLE'
    return 'PASS'


def validate_drc_report(result, schemas):
    from .report_contracts import validate_layout_report, validate_schema

    validate_schema(result, 'drc', schemas)
    # Saved receipts may be inspected on a different OS from the producer.
    raw_board = result['board']
    windows = '\\' in raw_board or bool(PureWindowsPath(raw_board).drive)
    board = PureWindowsPath(raw_board) if windows else PurePosixPath(raw_board)
    required_inputs = {board.with_suffix(suffix).name for suffix in ('.kicad_pcb', '.kicad_pro', '.kicad_dru')}
    if board.suffix != '.kicad_pcb' or not required_inputs <= result['input_sha256'].keys():
        raise ValueError('DRC input digests must include the board and both sidecars')
    board_digest = result['input_sha256'].get(board.name)
    if board_digest is None:
        raise ValueError('DRC input digests must include the reported board')
    layout = result['layout_report']
    if layout is not None:
        validate_layout_report(layout, schemas, board_sha256=board_digest)
        if result['identity'] != layout['identity']:
            raise ValueError('DRC identity differs from the embedded layout identity')
    elif result['identity'] is not None:
        raise ValueError('DRC without layout evidence must have null identity')
    fields = [name in result for name in NATIVE_FIELDS]
    if any(fields):
        if not all(fields) or 'reason' in result:
            raise ValueError('DRC native measurement fields must be complete and exclusive of failure reason')
        count = validate_native_report(result['report'])
        if result['finding_count'] != count:
            raise ValueError('DRC finding count differs from native findings')
        expected = 'PASS' if result['exit_code'] == 0 and count == 0 else 'FAIL'
        if result['drc_status'] != expected:
            raise ValueError('DRC status differs from native exit code and findings')
    elif result['drc_status'] not in ('NOT_RUN', 'FAIL') or not result.get('reason'):
        raise ValueError('DRC without native measurements must record a failure or unavailable-tool reason')
    if result['a4'] != result['drc_status']:
        raise ValueError('A4 differs from native DRC status')
    expected = aggregate_status({'status': result['drc_status']}, layout)
    if result['status'] != expected:
        raise ValueError('DRC aggregate status differs from native and layout evidence')
    return result
