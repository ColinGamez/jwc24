"""Actual local wheel install, outside checkout, with synthetic schedules only."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import venv
import zipfile

from tests.test_hbnj_publication import fixture, write_fixture


class HBNJInstalledWheelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if importlib.util.find_spec('setuptools') is None:
            raise unittest.SkipTest('Wheel verification needs the optional local setuptools build backend')
        cls.temporary = tempfile.TemporaryDirectory(prefix='jwc24-hbnj-wheel-')
        cls.root = Path(cls.temporary.name).resolve()
        # Check the exact root that TemporaryDirectory will recursively clean.
        if cls.root.parent != Path(tempfile.gettempdir()).resolve():
            raise AssertionError('Wheel test temporary root escaped the intended directory')
        cls.addClassCleanup(cls.temporary.cleanup)
        repository = Path(__file__).resolve().parents[1]
        source = Path(os.environ.get('JWC24_WHEEL_TEST_SOURCE', str(repository))).resolve()
        build_root = cls.root / 'build-source'
        build_root.mkdir()
        shutil.copyfile(source / 'pyproject.toml', build_root / 'pyproject.toml')
        shutil.copytree(source / 'jwc24', build_root / 'jwc24',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))
        cls.environment = {key: value for key, value in os.environ.items()
                           if key not in {'PYTHONPATH', 'PYTHONHOME'}}
        cls.environment['PIP_NO_INDEX'] = '1'
        cls.environment['PIP_CONFIG_FILE'] = os.devnull
        cls.environment['PYTHONIOENCODING'] = 'utf-8'
        wheels = cls.root / 'wheels'
        wheels.mkdir()
        result = subprocess.run([
            sys.executable, '-c',
            'from setuptools.build_meta import build_wheel; import sys; build_wheel(sys.argv[1])',
            str(wheels)], cwd=build_root, env=cls.environment,
            capture_output=True, timeout=120, check=False)
        if result.returncode:
            raise AssertionError('Local wheel build failed: ' + result.stderr.decode(errors='replace')[-3000:])
        wheel, = wheels.glob('*.whl')
        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())
            required = {f'jwc24/hbnj_validation/{name}.py' for name in ('__init__', 'guide', 'payloads', 'areas')}
            if not required <= names or any(name.startswith(('tools/', 'private/')) for name in names):
                raise AssertionError('Wheel validation code is missing or checkout/private data was included')
        virtual = cls.root / 'venv'
        venv.EnvBuilder(with_pip=True, system_site_packages=False).create(virtual)
        cls.python = virtual / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        result = subprocess.run([str(cls.python), '-m', 'pip', 'install', '--no-index', '--no-deps',
                                 '--disable-pip-version-check', str(wheel)],
                                cwd=cls.root, env=cls.environment, capture_output=True,
                                timeout=90, check=False)
        if result.returncode:
            raise AssertionError('Offline wheel installation failed: ' + result.stderr.decode(errors='replace')[-3000:])
        cls.input = cls.root / 'inputs'
        write_fixture(cls.input, fixture(int(time.time())))
        cls.probe_path = cls.root / 'probe.py'
        shutil.copyfile(repository / 'tests/_hbnj_wheel_probe.py', cls.probe_path)

    def probe(self, mode):
        working = self.root / mode
        working.mkdir()
        result = subprocess.run([str(self.python), '-I', str(self.probe_path), mode,
                                 str(self.input), str(working)],
                                cwd=working, env=self.environment, capture_output=True,
                                timeout=120, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace')[-5000:])
        self.assertIn(f'wheel-{mode}-verified', result.stdout.decode(errors='replace'))

    def test_installed_wheel_loads_and_rejects_invalid_content_without_tools(self):
        self.probe('validation')

    @unittest.skipUnless(shutil.which('openssl'), 'Installed-wheel AES transport probe requires local OpenSSL')
    def test_installed_wheel_serves_all_snapshot_routes_with_real_transport(self):
        self.probe('serving')
