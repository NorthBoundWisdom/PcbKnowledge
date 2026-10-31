"""Separate installed-KiCad process; never imported by catalog execution paths."""
from __future__ import annotations

import argparse
from pathlib import Path


def _path(root, value, *, exists=False):
    root = Path(root).resolve()
    path = Path(value)
    path = path if path.is_absolute() else root / path
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError('KiCad bridge paths must not traverse symlinks')
    path = path.resolve()
    if not path.is_relative_to(root / 'build') or path == root / 'build':
        raise ValueError('KiCad bridge files must be below build/')
    if exists and (not path.is_file() or path.stat().st_size > 32 * 1024 * 1024):
        raise ValueError('Missing or oversized KiCad bridge input')
    return path


def operate(root, action, board_path, output_path, session_path=None):
    """Optional pcbnew dependency exists only in this explicitly spawned process."""
    board_path = _path(root, board_path, exists=True)
    output = _path(root, output_path)
    if output.exists() or board_path.suffix != '.kicad_pcb':
        raise ValueError('KiCad bridge needs a board and a fresh separate output')
    expected_suffix = '.dsn' if action == 'export-dsn' else '.kicad_pcb'
    if output.suffix != expected_suffix or action not in ('export-dsn', 'merge-session', 'fill'):
        raise ValueError('Unsupported KiCad bridge action or output type')
    session = _path(root, session_path, exists=True) if session_path else None
    if (action == 'merge-session') != (session is not None):
        raise ValueError('Session input is required only for merge-session')
    import pcbnew
    project = board_path.with_suffix('.kicad_pro')
    if project.exists():
        _path(root, project, exists=True)
        if not pcbnew.GetSettingsManager().LoadProject(str(project)):
            raise ValueError('KiCad project settings could not be loaded')
    board = pcbnew.LoadBoard(str(board_path))
    if board is None:
        raise ValueError('KiCad could not load the derived board')
    if action == 'export-dsn':
        success = pcbnew.ExportSpecctraDSN(board, str(output))
    else:
        if action == 'merge-session' and not pcbnew.ImportSpecctraSES(board, str(session)):
            raise ValueError('KiCad rejected the router session')
        if action == 'fill':
            pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        success = pcbnew.SaveBoard(str(output), board)
    if success is False or not output.is_file() or output.stat().st_size == 0:
        raise ValueError('KiCad did not produce the requested output')
    print(pcbnew.Version())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('action', choices=('export-dsn', 'merge-session', 'fill'))
    parser.add_argument('board')
    parser.add_argument('output')
    parser.add_argument('--session')
    arguments = parser.parse_args()
    operate(arguments.root, arguments.action, arguments.board, arguments.output, arguments.session)


if __name__ == '__main__':
    main()
