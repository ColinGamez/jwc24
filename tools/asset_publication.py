"""Publish complete asset bytes without exposing partially written files."""
from __future__ import annotations

from contextlib import ExitStack
import os
import tempfile
from pathlib import Path

from jwc24.publication_lock import directory_lock

LOCK_TIMEOUT = 30.0


def _directory_lock(directory: Path):
    return directory_lock(directory, timeout=LOCK_TIMEOUT)

def _atomic_write_unlocked(path: Path, payload: bytes) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".asset-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write(path: Path, payload: bytes) -> None:
    path = path.resolve()
    with _directory_lock(path.parent):
        _atomic_write_unlocked(path, payload)


def publish_assets(assets: list[tuple[Path, bytes]], *, source_check: tuple[Path, bytes] | None = None,
                   source_checks: list[tuple[Path, bytes]] | None = None) -> None:
    """Serialize publishers and rollback ordinary errors within a batch.

    Optional source bytes are checked while holding every source directory lock
    along with all output locks. Source writers must share directory_lock for
    the check to remain valid throughout publication.
    """
    assets = [(path.resolve(), payload) for path, payload in assets]
    directories = {path.parent for path, _ in assets}
    checks = list(source_checks or [])
    if source_check is not None:
        checks.append(source_check)
    checks = [(path.resolve(), payload) for path, payload in checks]
    directories.update(path.parent for path, _ in checks)
    directories = sorted(directories, key=lambda path: os.path.normcase(str(path)))
    with ExitStack() as locks:
        for directory in directories:
            locks.enter_context(_directory_lock(directory))
        for path, captured in checks:
            if path.read_bytes() != captured:
                raise ValueError("source catalog changed during artwork generation")
        originals = {path: path.read_bytes() if path.exists() else None for path, _ in assets}
        published = []
        try:
            for path, payload in assets:
                _atomic_write_unlocked(path, payload)
                published.append(path)
        except BaseException:
            for path in reversed(published):
                if originals[path] is None:
                    path.unlink(missing_ok=True)
                else:
                    _atomic_write_unlocked(path, originals[path])
            raise
