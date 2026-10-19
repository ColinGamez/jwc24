import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import asset_publication


class AssetPublicationTests(unittest.TestCase):
    def test_replace_failure_preserves_published_file_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.img"
            path.write_bytes(b"old")
            with patch.object(asset_publication.os, "replace", side_effect=OSError("disk error")):
                with self.assertRaises(OSError):
                    asset_publication.atomic_write(path, b"new")
            self.assertEqual(path.read_bytes(), b"old")
            self.assertEqual(list(path.parent.glob(".asset-*")), [])

    def test_batch_failure_restores_prior_outputs_and_removes_new_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second, third = [root / name for name in ("first.img", "second.img", "third.img")]
            first.write_bytes(b"old")
            replace = asset_publication.os.replace
            def fail_third(source, target):
                if target == third:
                    raise OSError("failed third output")
                replace(source, target)
            with patch.object(asset_publication.os, "replace", side_effect=fail_third):
                with self.assertRaises(OSError):
                    asset_publication.publish_assets([(first, b"new"), (second, b"new"), (third, b"new")])
            self.assertEqual(first.read_bytes(), b"old")
            self.assertFalse(second.exists())
            self.assertFalse(third.exists())

    def test_failed_batch_cannot_rollback_over_concurrent_process(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first.img", root / "second.img"
            first.write_bytes(b"old")
            replace = asset_publication.os.replace
            child = None
            def fail_second(source, target):
                nonlocal child
                if target == second:
                    code = (
                        "from pathlib import Path; from tools.asset_publication import atomic_write; "
                        "print('waiting', flush=True); "
                        "atomic_write(Path(__import__('sys').argv[1]), b'concurrent'); "
                        "print('done', flush=True)"
                    )
                    child = subprocess.Popen([sys.executable, "-c", code, str(first)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    self.assertEqual(child.stdout.readline().strip(), "waiting")
                    # The batch still owns the lock while this separate process
                    # attempts publication. It must not finish before rollback.
                    import time
                    time.sleep(0.15)
                    self.assertIsNone(child.poll())
                    raise OSError("injected publication failure")
                replace(source, target)
            try:
                with patch.object(asset_publication.os, "replace", side_effect=fail_second):
                    with self.assertRaises(OSError):
                        asset_publication.publish_assets([(first, b"batch"), (second, b"batch")])
                stdout, stderr = child.communicate(timeout=10)
                self.assertEqual(child.returncode, 0, stderr)
                self.assertIn("done", stdout)
                self.assertEqual(first.read_bytes(), b"concurrent")
                self.assertFalse(second.exists())
            finally:
                if child is not None and child.poll() is None:
                    child.kill()
                    child.communicate()

    def test_lock_wait_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with asset_publication._directory_lock(root):
                with patch.object(asset_publication, "LOCK_TIMEOUT", 0):
                    with self.assertRaises(TimeoutError):
                        asset_publication.atomic_write(root / "image.img", b"new")
            self.assertFalse((root / "image.img").exists())

    def test_multiple_directories_are_locked_in_sorted_order(self):
        from contextlib import contextmanager
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seen = []
            @contextmanager
            def observe(path):
                path.mkdir(parents=True, exist_ok=True)
                seen.append(path)
                yield
            with patch.object(asset_publication, "_directory_lock", side_effect=observe):
                asset_publication.publish_assets([(root / "z" / "a.img", b"a"), (root / "a" / "b.img", b"b")])
            self.assertEqual(seen, [(root / "a").resolve(), (root / "z").resolve()])

    @unittest.skipUnless(__import__('os').name == 'nt', 'Windows locking API')
    def test_unexpected_windows_lock_failure_propagates(self):
        import msvcrt
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(msvcrt, 'locking', side_effect=OSError(5, 'unexpected I/O failure')) as lock:
                with self.assertRaises(OSError):
                    asset_publication.atomic_write(Path(directory) / 'image.img', b'new')
            self.assertEqual(lock.call_count, 1)

    def test_changed_or_missing_source_aborts_before_output_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root/'catalog.json', root/'image.img'
            output.write_bytes(b'old')
            source.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'source catalog changed'):
                asset_publication.publish_assets([(output,b'new')], source_check=(source,b'captured'))
            self.assertEqual(output.read_bytes(), b'old')
            source.unlink()
            with self.assertRaises(FileNotFoundError):
                asset_publication.publish_assets([(output,b'new')], source_check=(source,b'captured'))
            self.assertEqual(output.read_bytes(), b'old')

    def test_source_writer_waits_until_same_directory_assets_published(self):
        import subprocess
        import sys
        import time
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root/'catalog.json', root/'image.img'
            source.write_bytes(b'captured')
            replace = asset_publication.os.replace
            child = None
            def competing_writer(temporary, target):
                nonlocal child
                code = "from pathlib import Path; from tools.asset_publication import atomic_write; import sys; print('waiting',flush=True); atomic_write(Path(sys.argv[1]),b'refreshed')"
                child = subprocess.Popen([sys.executable,'-c',code,str(source)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                self.assertEqual(child.stdout.readline().strip(),'waiting')
                time.sleep(.15)
                self.assertIsNone(child.poll())
                replace(temporary,target)
            try:
                with patch.object(asset_publication.os,'replace',side_effect=competing_writer):
                    asset_publication.publish_assets([(output,b'new')],source_check=(source,b'captured'))
                stdout, stderr = child.communicate(timeout=10)
                self.assertEqual(child.returncode,0,stderr)
                self.assertEqual(output.read_bytes(),b'new')
                self.assertEqual(source.read_bytes(),b'refreshed')
            finally:
                if child is not None and child.poll() is None:
                    child.kill()
                    child.communicate()

    def test_changed_secondary_source_prevents_metadata_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, secondary = root / 'rooms.json', root / 'references' / 'revivals.json'
            secondary.parent.mkdir()
            output.write_bytes(b'original rooms')
            secondary.write_bytes(b'new references')
            with self.assertRaisesRegex(ValueError, 'source catalog changed'):
                asset_publication.publish_assets([(output, b'rebuilt rooms')], source_checks=[
                    (output, b'original rooms'), (secondary, b'old references')])
            self.assertEqual(output.read_bytes(), b'original rooms')
            self.assertEqual(secondary.read_bytes(), b'new references')

    def test_multiple_sources_lock_unique_directories_before_checking(self):
        from contextlib import contextmanager
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / 'z' / 'first.json', root / 'a' / 'second.csv'
            for path in (first, second):
                path.parent.mkdir()
                path.write_bytes(b'captured')
            held = []
            @contextmanager
            def observe(path):
                held.append(path)
                yield
            with patch.object(asset_publication, '_directory_lock', side_effect=observe):
                asset_publication.publish_assets([(first, b'new')],
                    source_check=(first, b'captured'), source_checks=[(second, b'captured')])
            self.assertEqual(held, [second.parent.resolve(), first.parent.resolve()])
            self.assertEqual(first.read_bytes(), b'new')
