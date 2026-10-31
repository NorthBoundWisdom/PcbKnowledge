"""Optional tool discovery and isolated external process execution for reference layout."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import threading
import zipfile

MAX_LOG_BYTES = 4 * 1024 * 1024


def derived_path(root, requested):
    root = Path(root).resolve()
    path = Path(requested)
    path = path if path.is_absolute() else root / path
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError('Reference layout paths must not traverse symlinks')
    path = path.resolve()
    if not path.is_relative_to(root / 'build') or path == root / 'build':
        raise ValueError('Reference layout files must be below build/')
    return path


def isolated_environment(directory):
    directory = Path(directory)
    env = os.environ.copy()
    for variable, name in (('HOME', 'home'), ('XDG_CONFIG_HOME', 'config'),
                           ('XDG_CACHE_HOME', 'cache'), ('XDG_DATA_HOME', 'data')):
        path = directory / name
        path.mkdir(parents=True, exist_ok=True)
        env[variable] = str(path)
    env['KICAD_CONFIG_HOME'] = str(directory / 'config')
    return env


def resolve_executable(explicit, name):
    """An invalid explicit choice never falls back to a different executable."""
    candidate = str(explicit) if explicit is not None else shutil.which(name)
    if candidate is None:
        return None
    path = Path(candidate).expanduser().absolute()
    return str(path) if path.is_file() and os.access(path, os.X_OK) else None


def _capture(command, directory, stream, timeout):
    overflow = threading.Event()
    process = subprocess.Popen(command, cwd=directory, env=isolated_environment(directory),
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    def drain():
        count = 0
        while True:
            chunk = process.stdout.read(65536)
            if not chunk:
                break
            available = MAX_LOG_BYTES - count
            stream.write(chunk[:available])
            count += len(chunk)
            if count > MAX_LOG_BYTES:
                overflow.set()
                process.kill()
                break
    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    reason = None
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        code = process.wait()
        reason = 'External tool exceeded its time limit'
    reader.join(timeout=5)
    process.stdout.close()
    if reader.is_alive():
        reason = 'External tool log reader did not finish'
    if overflow.is_set():
        reason = 'External tool log exceeds size limit'
    return code, reason


def run_process(argv, *, root, directory, timeout=120):
    """Capture logs on disk and return actual status; no shell or ambient settings."""
    directory = derived_path(root, directory)
    if directory.exists():
        raise ValueError('External process directory must be fresh')
    directory.mkdir(parents=True)
    output = directory / 'process.log'
    started = time.monotonic()
    command = [str(value) for value in argv]
    result = {'command': command, 'status': 'FAIL', 'log': str(output)}
    with output.open('wb') as stream:
        try:
            code, reason = _capture(command, directory, stream, timeout)
            result.update(exit_code=code, status='PASS' if code == 0 and reason is None else 'FAIL')
            if reason:
                result['reason'] = reason
        except OSError as error:
            result.update(reason=str(error), exit_code=None)
    result['runtime_seconds'] = round(time.monotonic() - started, 6)
    return result


def _probe(executable, arguments, *, missing_code=None):
    if executable is None:
        return {'status': 'NOT_FOUND', 'path': None}
    with tempfile.TemporaryDirectory(prefix='pcbknowledge-tool-probe-') as temporary:
        try:
            process = subprocess.run([executable, *arguments], capture_output=True, text=True,
                                     timeout=20, env=isolated_environment(Path(temporary)), check=False)
            text = (process.stdout + process.stderr).strip()
            if missing_code is not None and process.returncode == missing_code:
                return {'status': 'NOT_FOUND', 'path': executable}
            if len(text.encode()) > 65536 or process.returncode:
                return {'status': 'FAIL', 'path': executable, 'reason': 'Version probe failed'}
            return {'status': 'FOUND', 'path': executable, 'version': text}
        except (OSError, subprocess.TimeoutExpired) as error:
            return {'status': 'FAIL', 'path': executable, 'reason': str(error)}


def _jar_version(java, jar):
    if java['status'] != 'FOUND':
        return {'version': 'NOT_RUN'}
    with tempfile.TemporaryDirectory(prefix='pcbknowledge-router-probe-') as temporary:
        argv = ['-Djava.awt.headless=true', '-jar', str(jar), '--help', '--gui.enabled=false',
                '--api_server.enabled=false', '-da', '--user_data_path=' + temporary]
        probe = _probe(java['path'], argv)
    if probe['status'] != 'FOUND':
        return {'status': 'FAIL', 'reason': 'Freerouting version probe failed'}
    match = re.search(r'Freerouting v(\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.]+)?)', probe['version'])
    if match is None:
        return {'status': 'FAIL', 'reason': 'Freerouting did not report its version'}
    return {'version': match.group(1)}


def locate_tools(*, kicad=None, java=None, freerouting=None, kicad_python=None):
    result = {'kicad': _probe(resolve_executable(kicad, 'kicad-cli'), ['version']),
              'java': _probe(resolve_executable(java, 'java'), ['-version'])}
    python = resolve_executable(kicad_python, 'python3')
    code = ('import importlib.util,sys; '
            'sys.exit(3) if importlib.util.find_spec("pcbnew") is None else None; '
            'import pcbnew; print(pcbnew.Version())')
    result['kicad_python'] = _probe(python, ['-c', code], missing_code=3)
    jar = Path(freerouting).expanduser().absolute() if freerouting is not None else None
    if jar is None or not jar.is_file():
        result['freerouting'] = {'status': 'NOT_FOUND', 'path': None}
        return result
    try:
        with zipfile.ZipFile(jar) as archive:
            manifest = archive.read('META-INF/MANIFEST.MF').decode('utf-8')
        fields = dict(line.split(': ', 1) for line in manifest.splitlines() if ': ' in line)
        if fields.get('Main-Class') != 'app.freerouting.Freerouting':
            raise ValueError('Jar is not the Freerouting executable')
        result['freerouting'] = {'status': 'FOUND', 'path': str(jar),
                                'sha256': hashlib.sha256(jar.read_bytes()).hexdigest(),
                                'manifest': fields}
        result['freerouting'].update(_jar_version(result['java'], jar))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        result['freerouting'] = {'status': 'FAIL', 'path': str(jar), 'reason': str(error)}
    return result


def run_router(dsn, session, tools, *, root, directory):
    dsn, session = derived_path(root, dsn), derived_path(root, session)
    if not dsn.is_file() or session.exists():
        raise ValueError('Router requires a DSN and a fresh session output')
    if any(tools[key]['status'] == 'NOT_FOUND' for key in ('java', 'freerouting')):
        return {'status': 'NOT_RUN', 'reason': 'Java or Freerouting is unavailable', 'runtime_seconds': 0}
    if any(tools[key]['status'] != 'FOUND' for key in ('java', 'freerouting')):
        return {'status': 'FAIL', 'reason': 'Java or Freerouting probe failed', 'runtime_seconds': 0}
    directory = derived_path(root, directory)
    command = [tools['java']['path'], '-Djava.awt.headless=true', '-jar', tools['freerouting']['path'],
               '-de', str(dsn), '-do', str(session), '--gui.enabled=false', '--api_server.enabled=false', '-da',
               '--user_data_path=' + str(directory / 'router-settings'), '--router.autorouter.max_passes=100',
               '--router.optimizer.max_passes=20', '--router.optimizer.max_threads=1', '-is', 'sequential']
    result = run_process(command, root=root, directory=directory, timeout=1800)
    if result['status'] == 'PASS' and (not session.is_file() or session.stat().st_size == 0):
        result.update(status='FAIL', reason='Router did not produce a session')
    return result


def run_bridge(action, board, output, tools, *, root, directory, session=None):
    board, output = derived_path(root, board), derived_path(root, output)
    if not board.is_file() or output.exists():
        raise ValueError('KiCad bridge requires a board and fresh output')
    tool = tools['kicad_python']
    if tool['status'] == 'NOT_FOUND':
        return {'status': 'NOT_RUN', 'reason': 'Installed KiCad Python bridge is unavailable'}
    if tool['status'] != 'FOUND':
        return {'status': 'FAIL', 'reason': 'Installed KiCad Python bridge probe failed'}
    helper = Path(__file__).with_name('kicad_bridge.py')
    command = [tool['path'], str(helper), str(Path(root).resolve()), action, str(board), str(output)]
    if session is not None:
        command.extend(['--session', str(derived_path(root, session))])
    result = run_process(command, root=root, directory=directory, timeout=180)
    if result['status'] == 'PASS' and (not output.is_file() or output.stat().st_size == 0):
        result.update(status='FAIL', reason='KiCad bridge did not produce its output')
    return result
