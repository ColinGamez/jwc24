"""Actual OS lock regressions, including a contended empty lockfile."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from jwc24.publication_lock import directory_lock


@contextmanager
def raw_lock(path):
    """Independent platform primitive; deliberately leave the file empty."""
    with path.open('r+b') as stream:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class PublicationLockTests(unittest.TestCase):
    def test_contended_empty_file_waits_without_initialization_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lockfile = root / '.publication.lock'
            lockfile.touch()
            def contender():
                with directory_lock(root, timeout=3):
                    return 'entered'
            with ThreadPoolExecutor(max_workers=1) as pool:
                with raw_lock(lockfile):
                    pending = pool.submit(contender)
                    # A permission error from initialization is a regression;
                    # a held lock must wait rather than failing before retry.
                    with self.assertRaises(FutureTimeout):
                        pending.result(timeout=0.1)
                    self.assertEqual(lockfile.stat().st_size, 0)
                self.assertEqual(pending.result(timeout=3), 'entered')
            self.assertEqual(lockfile.read_bytes(), b'')

    def test_real_child_process_excludes_and_releases(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            code = (
                'from pathlib import Path\n'
                'import sys\n'
                'from jwc24.publication_lock import directory_lock\n'
                '(Path(sys.argv[1]) / ".child-ready").touch()\n'
                'with directory_lock(Path(sys.argv[1]), timeout=5):\n'
                '    print("entered", flush=True)\n'
            )
            child = None
            try:
                with directory_lock(root):
                    child = subprocess.Popen([sys.executable, '-c', code, str(root)],
                        cwd=Path(__file__).resolve().parents[1],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    deadline = time.monotonic() + 3
                    while not (root / '.child-ready').exists() and child.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.01)
                    self.assertTrue((root / '.child-ready').exists(), 'child did not reach lock acquisition')
                    with self.assertRaises(subprocess.TimeoutExpired):
                        child.communicate(timeout=0.1)
                output, errors = child.communicate(timeout=5)
                self.assertEqual(child.returncode, 0, errors)
                self.assertEqual(output.strip(), 'entered')
                with directory_lock(root, timeout=0.1):
                    self.assertEqual((root / '.publication.lock').stat().st_size, 0)
            finally:
                if child is not None:
                    if child.poll() is None:
                        child.kill()
                    child.communicate(timeout=5)

    def test_exception_releases_without_deleting_or_replacing_lockfile(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(RuntimeError, 'synthetic'):
                with directory_lock(root):
                    identity = (root / '.publication.lock').stat().st_ino
                    raise RuntimeError('synthetic')
            path = root / '.publication.lock'
            self.assertTrue(path.is_file())
            self.assertEqual(path.stat().st_ino, identity)
            with directory_lock(root, timeout=0.1):
                self.assertEqual(path.stat().st_size, 0)
            self.assertEqual(path.stat().st_ino, identity)

    def test_contention_times_out_and_existing_file_bytes_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / '.publication.lock'
            path.write_bytes(b'existing lock marker')
            with raw_lock(path):
                with self.assertRaises(TimeoutError):
                    with directory_lock(root, timeout=0.03):
                        self.fail('contended lock entered')
            self.assertEqual(path.read_bytes(), b'existing lock marker')
            with directory_lock(root, timeout=0.1):
                pass


if __name__ == '__main__':
    unittest.main()
