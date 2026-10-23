import hashlib
import struct
import unittest

from tools.audit_wii_shop_client import is_dol, routes, shared_names, verify_content


class ShopClientAuditTests(unittest.TestCase):
    def test_content_size_and_hash_both_required(self):
        data = b'synthetic title content'
        digest = hashlib.sha1(data).digest()
        self.assertEqual(verify_content(data, len(data), digest), hashlib.sha256(data).hexdigest())
        for size, expected in ((len(data)+1, digest), (len(data), bytes(20))):
            with self.assertRaises(ValueError):
                verify_content(data, size, expected)

    def test_shared_map_names_and_duplicates(self):
        row = b'000000af'+bytes(range(20))
        self.assertEqual(shared_names(row)[bytes(range(20))], '000000af')
        for data in (row[:-1], row+row, b'../evil!'+bytes(20)):
            with self.assertRaises(ValueError):
                shared_names(data)

    def test_route_output_excludes_query_fragment_userinfo_and_other_hosts(self):
        data = (b'https://user:secret@oss-auth.shop.wii.com/startup?token=private#fragment\0'
                b'https://unknown.example/private\0')
        self.assertEqual(routes(data), [{'scheme': 'https', 'host': 'oss-auth.shop.wii.com', 'path': '/startup'}])

    def test_dol_requires_bounded_executable_entry(self):
        data = bytearray(0x104)
        struct.pack_into('>I', data, 0, 0x100)
        struct.pack_into('>I', data, 0x48, 0x80004000)
        struct.pack_into('>I', data, 0x90, 4)
        struct.pack_into('>I', data, 0xe0, 0x80004000)
        self.assertTrue(is_dol(data))
        struct.pack_into('>I', data, 0xe0, 0x4000)
        self.assertTrue(is_dol(data))
        struct.pack_into('>I', data, 0xe0, 0x80005000)
        self.assertFalse(is_dol(data))
        self.assertFalse(is_dol(b'not a DOL'))
