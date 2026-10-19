import hashlib
import struct
import unittest
from unittest.mock import patch

from tools import patch_demae_fixture_endpoint as patcher


class EndpointPatchTests(unittest.TestCase):
    def test_only_expected_fields_change_and_instruction_mismatch_rejected(self):
        data = bytearray(1536)
        struct.pack_into('>I', data, 0, 0x100)
        struct.pack_into('>I', data, 0x48, 0x800f9000)
        struct.pack_into('>I', data, 0x90, 0x200)
        struct.pack_into('>I', data, 4, 0x400)
        struct.pack_into('>I', data, 0x4c, 0x80077c00)
        struct.pack_into('>I', data, 0x94, 0x80)
        data[0x414:0x418] = bytes.fromhex('39000001')
        for index, offset, address, word in ((2, 0x480, 0x8002c280, '7d1c4378'),
                                           (3, 0x500, 0x8002c6c0, '7d134378')):
            struct.pack_into('>I', data, index*4, offset)
            struct.pack_into('>I', data, 0x48+index*4, address)
            struct.pack_into('>I', data, 0x90+index*4, 0x80)
            position = offset + (0x18 if index == 2 else 0x14)
            data[position:position+4] = bytes.fromhex(word)
        for offset in (0x1c0, 0x2b8):
            data[offset:offset+4] = bytes.fromhex('39000001')
        for offset, suffix in ((0x320, b'/nwapi.php?action='), (0x380, b'/nwapi.php')):
            value = b'nwapi.demae-can.com' + suffix + b'\0'
            data[offset:offset+len(value)] = value
        with patch.object(patcher, 'SOURCE_SHA256', hashlib.sha256(data).hexdigest()):
            result = patcher.patch_dol(bytes(data))
        self.assertEqual(len(result), len(data))
        self.assertEqual(result[0x1c0:0x1c4], bytes.fromhex('39000000'))
        self.assertEqual(result[0x2b8:0x2bc], bytes.fromhex('39000000'))
        self.assertEqual(result[:0x1c0], data[:0x1c0])
        self.assertEqual(result[0x1c4:0x2b8], data[0x1c4:0x2b8])
        self.assertIn(b'127.0.0.1:18085/nwapi.php?action=\0', result)
        self.assertEqual(result[0x414:0x418], bytes.fromhex('39000001'))
        with patch.object(patcher, 'SOURCE_SHA256', hashlib.sha256(data).hexdigest()):
            with_auth = patcher.patch_dol(bytes(data), include_auth=True)
        self.assertEqual(with_auth[0x414:0x418], bytes.fromhex('39000000'))
        with patch.object(patcher, 'SOURCE_SHA256', hashlib.sha256(data).hexdigest()):
            common = patcher.patch_dol(bytes(data), all_api_http=True)
        self.assertEqual(common[0x498:0x49c], bytes.fromhex('3b800000'))
        self.assertEqual(common[0x514:0x518], bytes.fromhex('3a600000'))
        data[0x1c0] = 0
        with patch.object(patcher, 'SOURCE_SHA256', hashlib.sha256(data).hexdigest()), self.assertRaises(ValueError):
            patcher.patch_dol(bytes(data))

    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            patcher.patch_dol(b'unknown')
