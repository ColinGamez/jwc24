import hashlib
import struct
import unittest
from tools.demae_native_hook_support import append_reserved_text, branch_instruction, replace_text_instruction, fill_owned_text_padding
from tools.inspect_demae_references import sections


class HookSupportTests(unittest.TestCase):
    def fixture(self):
        data = bytearray(0x104)
        struct.pack_into('>I', data, 0, 0x100)
        struct.pack_into('>I', data, 0x48, 0x80004000)
        struct.pack_into('>I', data, 0x90, 4)
        data[0x100:] = b'\x60\0\0\0'
        return bytes(data)

    def test_section_append_and_instruction_guards(self):
        source = self.fixture()
        result = append_reserved_text(source, b'\x4e\x80\0\x20', expected_sha256=hashlib.sha256(source).hexdigest())
        self.assertEqual(result[0x100:0x104], source[0x100:])
        self.assertGreater(len(result), len(source))
        reserved = next(row for row in sections(result) if row[2] == 0x80001800)
        self.assertEqual(reserved[3], 32)
        self.assertEqual(result[reserved[1]:reserved[1]+4], b'\x4e\x80\0\x20')
        self.assertEqual(result[reserved[1]+4:reserved[1]+32], bytes(28))
        patch = branch_instruction(0x80004000, 0x80001800)
        replaced = replace_text_instruction(result, 0x80004000, expected=source[0x100:], replacement=patch)
        self.assertEqual(replaced[0x100:0x104], patch)
        with self.assertRaises(ValueError):
            replace_text_instruction(replaced, 0x80004000, expected=source[0x100:], replacement=patch)
        with self.assertRaises(ValueError):
            append_reserved_text(source, b'\0'*4, expected_sha256='wrong')

    def test_branch_range_and_reserved_overlap(self):
        self.assertEqual(branch_instruction(0x1000, 0x1010), b'\x48\0\0\x10')
        for target in (0x1011, 0x2001000):
            with self.assertRaises(ValueError):
                branch_instruction(0x1000, target)
        source = bytearray(self.fixture())
        struct.pack_into('>II', source, 0xd8, 0x80001800, 4)
        with self.assertRaises(ValueError):
            append_reserved_text(bytes(source), b'\0'*4, expected_sha256=hashlib.sha256(source).hexdigest())

    def test_owned_padding_preserves_loader_header_and_guards_existing_bytes(self):
        source = bytearray(self.fixture())
        source.extend(bytes(0x24e0 - 4))
        struct.pack_into('>I', source, 0x90, 0x24e0)
        source = bytes(source)
        digest = hashlib.sha256(source).hexdigest()
        payload = b'\x4e\x80\0\x20' * 242
        result = fill_owned_text_padding(source, payload, expected_sha256=digest)
        position = 0x100 + 0x18c0
        self.assertEqual(len(result), len(source))
        self.assertEqual(result[:position], source[:position])
        self.assertEqual(result[position:position+len(payload)], payload)
        self.assertEqual(result[position+len(payload):], source[position+len(payload):])
        with self.assertRaises(ValueError):
            fill_owned_text_padding(result, payload, expected_sha256=hashlib.sha256(result).hexdigest())
        with self.assertRaises(ValueError):
            fill_owned_text_padding(source, bytes(1220), expected_sha256=digest)
