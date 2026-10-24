import unittest

from tools.prepare_vwii_credentials import convert_otp


class VwiiCredentialTests(unittest.TestCase):
    def test_only_vwii_banks_are_mapped_to_bootmii_layout(self):
        data = bytes(range(256))*4
        result = convert_otp(data)
        self.assertEqual(len(result), 1024)
        self.assertEqual(result[0x100:0x180], data[:0x80])
        self.assertEqual(result[0x200:0x248], data[0x300:0x348])
        self.assertEqual(result[0x274:0x284], data[0x348:0x358])
        self.assertEqual(result[0x180:0x200], bytes(0x80))
        self.assertEqual(result[0x248:0x274], bytes(0x2c))
        self.assertEqual(result[0x300:], bytes(0x100))
        self.assertNotIn(b'ConsoleID', result[:0x100])

    def test_wrong_size_empty_or_default_credentials_are_rejected(self):
        for data in (b'', bytes(1023), bytes(1025), bytes(1024), b'\xff'*1024):
            with self.assertRaises(ValueError):
                convert_otp(data)
        data = bytearray(bytes(range(256))*4)
        data[0x24:0x28] = bytes.fromhex('0403ac68')
        with self.assertRaisesRegex(ValueError, 'default device'):
            convert_otp(bytes(data))
