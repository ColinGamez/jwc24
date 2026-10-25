import unittest
from types import SimpleNamespace

class WADExtractionMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from tools.extract_wad_contents import title_metadata
        except ModuleNotFoundError as error:
            if error.name == 'libWiiPy':
                raise unittest.SkipTest('Optional WAD extraction dependency unavailable') from None
            raise
        cls.title_metadata = staticmethod(title_metadata)

    def test_binary_identifier_preserves_leading_bytes_and_boot_metadata(self):
        ticket = SimpleNamespace(title_id=bytes.fromhex("000100014841544a"))
        tmd = SimpleNamespace(title_id="000100014841544a", title_version=1792,
                              boot_index=12, ios_version=55)
        self.assertEqual(self.title_metadata(ticket, tmd), {
            "title_id": "000100014841544A", "title_version": 1792,
            "boot_index": 12, "required_ios": 55})

    def test_mismatched_or_truncated_identifier_is_rejected(self):
        tmd = SimpleNamespace(title_id="000100014841544A")
        for raw in (bytes.fromhex("000100014841504a"), b"HATJ"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.title_metadata(SimpleNamespace(title_id=raw), tmd)
