"""File helpers shared across modules."""

from __future__ import annotations

import os
import re
import socket
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from kahnban import frontmatter


def write_text_atomic(path: Path, text: str) -> None:
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}.{time.time_ns()}")
    try:
        temp_path.write_text(frontmatter.normalize_newlines(text), encoding="utf-8", newline="\n")
        temp_path.replace(path)
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def unlink_retry(path: Path, *, tries: int = 200) -> None:
    """Remove a file another process may have open for a moment.

    Waiters read a lock to see who holds it, and on Windows a file with a reader cannot be
    deleted: the holder's release then fails, silently, and the lock stays forever.
    """
    for _ in range(tries):
        try:
            path.unlink()
            return
        except FileNotFoundError:
            return
        except PermissionError:
            time.sleep(0.005)
    path.unlink(missing_ok=True)


def process_alive(pid: int) -> bool:
    """True when a process with this id is running (or when we cannot tell it is not)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied: it exists, we may not look
        try:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def lock_stamp(extra: str = "") -> str:
    """What a lock file says about its holder: who, where and when."""
    return f"pid={os.getpid()} host={socket.gethostname()} at={time.strftime('%Y-%m-%dT%H:%M:%S')}{extra}\n"


def holder_is_dead(stamp: str) -> bool:
    """True when the lock's text names a process on this machine that no longer exists.

    A lock with no pid (an older stamp, or an empty file) or from another host cannot be judged, so
    it stays held until the age rule says otherwise: waiting is safe, breaking a live lock is not.
    """
    pid = re.search(r"\bpid=(\d+)", stamp)
    if not pid:
        return False
    host = re.search(r"\bhost=(\S+)", stamp)
    if host and host.group(1) != socket.gethostname():
        return False
    return not process_alive(int(pid.group(1)))


def break_lock(path: Path, seen: str) -> bool:
    """Take down the lock at ``path`` if it still says ``seen``. True for the one caller that did.

    Waiters that judge the same lock stale race for a guard file made with exclusive create, the one
    primitive the locks themselves rest on (concurrent renames of one file all reported success on
    the Windows machine this was written on). Only the guard's owner removes the lock, and only
    after reading that it is still the one that was judged, so a lock made in the meantime stays.
    """
    guard = path.with_name(path.name + ".breaking")
    try:
        os.close(os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except OSError:
        try:
            if time.time() - guard.stat().st_mtime > 10:  # its owner died mid-break
                guard.unlink()
        except OSError:
            pass
        return False
    try:
        try:
            current = path.read_text(encoding="utf-8")
        except OSError:
            return False  # already gone
        if current.strip() != seen.strip():
            return False
        unlink_retry(path)
        return True
    except OSError:
        return False
    finally:
        unlink_retry(guard)


@contextmanager
def exclusive(path: Path, *, wait: float = 10.0, stale: float = 30.0) -> Iterator[None]:
    """Hold a lock file at ``path`` while the block runs.

    Waits up to ``wait`` seconds. A lock whose holder is a dead process on this machine is broken at
    once; any other lock older than ``stale`` seconds is assumed to belong to a process that died
    and is broken too (the holds here last milliseconds, so ``stale`` stays far above any real hold
    and well above ``wait``). Windows reports a lock file that another process is deleting as
    ``PermissionError`` rather than ``FileExistsError``, so both mean "try again".
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, lock_stamp().encode())
            os.close(descriptor)
            break
        except (FileExistsError, PermissionError):
            try:
                seen = path.read_text(encoding="utf-8")
                old = time.time() - path.stat().st_mtime > stale
            except OSError:
                continue  # it vanished between the open and the read: the holder just finished
            if (old or holder_is_dead(seen)) and break_lock(path, seen):
                continue
            if time.monotonic() > deadline:
                raise TimeoutError(f"could not lock {path}")
            time.sleep(0.02)
    try:
        yield
    finally:
        try:
            unlink_retry(path)
        except OSError:
            pass
