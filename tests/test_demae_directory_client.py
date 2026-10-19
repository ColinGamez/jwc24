import hashlib
import struct
import unittest
from pathlib import Path
import importlib.util
from unittest.mock import patch
from tools.build_demae_directory_client import patch_directory_filter, FILTER_ADDRESS
from tools.build_demae_directory_client import patch_directory_images, LOGO_PREFIX_ADDRESS, LOGO_HTTPS_ADDRESS
from tools.inspect_demae_references import sections


def fixture():
    data = bytearray(0x300)
    struct.pack_into('>I', data, 0, 0x100)
    struct.pack_into('>I', data, 0x48, 0x80038D00)
    struct.pack_into('>I', data, 0x90, 0x200)
    offset = 0x100 + FILTER_ADDRESS - 0x80038D00
    data[offset:offset+4] = bytes.fromhex('41820170')
    return bytes(data), offset


class DirectoryClientTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('unicorn'), 'Optional Unicorn dependency')
    def test_native_logo_builder_uses_local_http_with_only_reviewed_bytes_changed(self):
        path = Path(__file__).resolve().parents[1] / 'private/demae/fixtures/HCHJ-local-api.dol'
        if not path.exists():
            self.skipTest('Private source unavailable')
        source = path.read_bytes()
        result = patch_directory_images(source)
        allowed = set()
        for _, offset, base, size in sections(source):
            for address, length in ((LOGO_PREFIX_ADDRESS, len(b'nwpic.demae-can.com/logoimg2/\0')),
                                    (LOGO_HTTPS_ADDRESS, 4)):
                if base <= address < base+size:
                    allowed.update(range(offset+address-base, offset+address-base+length))
        self.assertEqual(len(result), len(source))
        self.assertTrue(all(position in allowed for position, (old, new) in enumerate(zip(source, result)) if old != new))
        from tools.verify_demae_area_request import verify
        self.assertEqual(verify(result, 'hotpepper:J000000001', logo=True,
                                expected_sha256=hashlib.sha256(result).hexdigest()),
                         'http://127.0.0.1:18085/logoimg2/hotpepper:J000000001.jpg')
        with self.assertRaises(ValueError):
            patch_directory_images(result)

    def test_only_reviewed_branch_changes_and_dol_header_is_preserved(self):
        source, offset = fixture()
        with patch('tools.build_demae_directory_client.SOURCE_SHA', hashlib.sha256(source).hexdigest()):
            result = patch_directory_filter(source)
        self.assertEqual(result[:offset], source[:offset])
        self.assertEqual(result[offset:offset+4], bytes.fromhex('60000000'))
        self.assertEqual(result[offset+4:], source[offset+4:])

    def test_unknown_source_and_changed_instruction_are_rejected(self):
        source, offset = fixture()
        with self.assertRaises(ValueError):
            patch_directory_filter(source)
        damaged = source[:offset] + bytes(4) + source[offset+4:]
        with patch('tools.build_demae_directory_client.SOURCE_SHA', hashlib.sha256(damaged).hexdigest()):
            with self.assertRaises(ValueError):
                patch_directory_filter(damaged)
