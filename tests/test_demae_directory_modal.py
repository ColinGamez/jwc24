import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.build_demae_directory_client import patch_directory_modal, FILTER_ADDRESS, ROW_TRANSITION, JOB_SLOT
from tools.verify_demae_directory_modal import verify

ROOT = Path(__file__).resolve().parents[1]
TOOLCHAIN = Path('C:/devkitPro/devkitPPC/bin')
AVAILABLE = TOOLCHAIN.joinpath('powerpc-eabi-as.exe').is_file() and importlib.util.find_spec('unicorn') is not None


@unittest.skipUnless(AVAILABLE, 'Optional PowerPC toolchain and Unicorn required')
class CompiledDirectoryModalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT/'private').mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(prefix='directory-modal-test-', dir=ROOT/'private')
        prefix = Path(cls.temp.name)/'payload'
        subprocess.run([sys.executable, str(ROOT/'tools/build_demae_directory_modal.py'),
                        '--output-prefix', str(prefix)], check=True, capture_output=True)
        cls.payload = Path(str(prefix)+'.bin').read_bytes()
        cls.metadata = json.loads(Path(str(prefix)+'.metadata.json').read_bytes())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def source(self):
        data = bytearray(0x82200)
        for index, offset, address, size in [(0, 0x100, 0x80004000, 0x2000),
                                             (1, 0x2100, 0x80038000, 0x80000),
                                             (7, 0x82100, 0x80344700, 0x100)]:
            struct.pack_into('>I', data, index*4, offset)
            struct.pack_into('>I', data, 0x48+index*4, address)
            struct.pack_into('>I', data, 0x90+index*4, size)
        for address, word in [(FILTER_ADDRESS, 0x41820170), (ROW_TRANSITION, 0x38600104),
                              (0x800AA2DC, 0x9421FF80)]:
            struct.pack_into('>I', data, 0x2100+address-0x80038000, word)
        struct.pack_into('>I', data, 0x82100+JOB_SLOT-0x80344700, 0x800B75C4)
        return bytes(data)

    def test_actual_compiled_payload_control_flow_and_sdk_boundaries(self):
        self.assertGreaterEqual(verify(self.payload, self.metadata), 20)

    def test_patcher_preserves_header_and_guards_original_cleanup_and_job_slot(self):
        source = self.source()
        with patch('tools.build_demae_directory_client.SOURCE_SHA', hashlib.sha256(source).hexdigest()):
            result, scenarios = patch_directory_modal(source, self.payload, self.metadata)
        self.assertEqual(result[:256], source[:256])
        self.assertGreaterEqual(scenarios, 20)
        for offset in (0x2100+0x800AA2DC-0x80038000, 0x82100+JOB_SLOT-0x80344700):
            changed = source[:offset]+bytes(4)+source[offset+4:]
            with patch('tools.build_demae_directory_client.SOURCE_SHA', hashlib.sha256(changed).hexdigest()):
                with self.assertRaises(ValueError):
                    patch_directory_modal(changed, self.payload, self.metadata)
