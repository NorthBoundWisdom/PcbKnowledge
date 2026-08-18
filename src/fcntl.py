"""Minimal cross-platform compatibility for the flock subset used by PcbKnowledge.

The repository core historically imported POSIX ``fcntl`` directly. Keeping this
module at the source root preserves that import while providing the exact
``flock(fd, LOCK_EX|LOCK_UN)`` subset on Windows without a third-party runtime
dependency. POSIX uses the native libc ``flock(2)`` primitive so locks keep
open-file-description semantics even between repository instances in one process.
No other fcntl API is intentionally emulated.
"""

from __future__ import annotations

import os


LOCK_EX = 2
LOCK_UN = 8


def _windows_flock(fd: int, operation: int) -> None:
    import msvcrt

    position = os.lseek(fd, 0, os.SEEK_CUR)
    try:
        if os.fstat(fd).st_size == 0:
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, b"\0")
            os.fsync(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        mode = msvcrt.LK_LOCK if operation == LOCK_EX else msvcrt.LK_UNLCK
        msvcrt.locking(fd, mode, 1)
    finally:
        os.lseek(fd, position, os.SEEK_SET)


def _posix_flock(fd: int, operation: int) -> None:
    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    native_flock = libc.flock
    native_flock.argtypes = (ctypes.c_int, ctypes.c_int)
    native_flock.restype = ctypes.c_int
    if native_flock(fd, operation) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


def flock(fd: int, operation: int) -> None:
    """Acquire or release the exclusive repository lock used by the store."""

    if operation not in {LOCK_EX, LOCK_UN}:
        raise ValueError(f"unsupported flock operation: {operation}")
    if os.name == "nt":
        _windows_flock(fd, operation)
    else:
        _posix_flock(fd, operation)
