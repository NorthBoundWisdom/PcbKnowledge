"""Minimal cross-platform compatibility for the flock subset used by PcbKnowledge.

The repository core historically imported POSIX ``fcntl`` directly. Keeping this
module at the source root preserves that import while providing the exact
``flock(fd, LOCK_EX|LOCK_UN)`` subset on Windows without a third-party runtime
dependency. No other fcntl API is intentionally emulated.
"""

from __future__ import annotations

import os


LOCK_EX = 2
LOCK_UN = 8


def _ensure_lock_byte(fd: int) -> None:
    """Ensure byte-range locking has one stable byte without changing position."""

    position = os.lseek(fd, 0, os.SEEK_CUR)
    try:
        if os.fstat(fd).st_size == 0:
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, b"\0")
            os.fsync(fd)
    finally:
        os.lseek(fd, position, os.SEEK_SET)


def flock(fd: int, operation: int) -> None:
    """Acquire or release the exclusive repository lock used by the store."""

    if operation not in {LOCK_EX, LOCK_UN}:
        raise ValueError(f"unsupported flock operation: {operation}")

    _ensure_lock_byte(fd)
    os.lseek(fd, 0, os.SEEK_SET)

    if os.name == "nt":
        import msvcrt

        mode = msvcrt.LK_LOCK if operation == LOCK_EX else msvcrt.LK_UNLCK
        msvcrt.locking(fd, mode, 1)
        return

    if not hasattr(os, "lockf"):
        raise OSError("platform does not provide a supported file-lock primitive")
    command = os.F_LOCK if operation == LOCK_EX else os.F_ULOCK
    os.lockf(fd, command, 1)
