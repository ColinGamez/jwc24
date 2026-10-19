"""Cross-process directory lock for catalog and artwork publishers."""
from contextlib import contextmanager
import errno
import os
import time
from pathlib import Path


@contextmanager
def directory_lock(directory: Path, timeout: float = 30.0):
    directory.mkdir(parents=True, exist_ok=True)
    # Never remove the lockfile: removing it can split waiting publishers
    # across different inodes. Only byte zero is locked on Windows.
    with (directory / ".publication.lock").open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as error:
                # Windows lock contention is EACCES with ERROR_LOCK_VIOLATION;
                # an actual permission failure must propagate immediately.
                contention = (getattr(error, "winerror", None) == 33 or
                              (getattr(error, "winerror", None) is None and
                               error.errno in (errno.EACCES, errno.EAGAIN))) if os.name == "nt" else error.errno in (errno.EACCES, errno.EAGAIN)
                if not contention:
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for publication lock: {directory}") from error
                time.sleep(0.01)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
