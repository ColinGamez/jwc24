"""Synthetic list-reference construction, without fetching catalogs or media."""
from pathlib import Path
import struct
import unittest

from jwc24.forecast import encode_lz10
from jwc24.lz11 import encode_lz11
from jwc24.nintendo_references import build_japanese_list_reference
from tests.test_nintendo_csdata import synthetic_csdata, with_crc


def fixture(identifier=0, reference=b'synthetic-directory'):
    raw = bytearray(synthetic_csdata(reference=reference))
    struct.pack_into('>I', raw, 0x0C, identifier)
    return with_crc(raw)


class NintendoReferenceTests(unittest.TestCase):
    prefix = b'https://synthetic.invalid/base/'

    def build(self, payload=None, **kwargs):
        return build_japanese_list_reference(
            payload if payload is not None else fixture(),
            service_prefix=kwargs.get('service_prefix', self.prefix),
            language_code=kwargs.get('language_code', 0),
        )

    def test_identifier_is_unsigned_decimal_filename_not_claimed_timestamp(self):
        for identifier in (0, 1, 4294967295):
            result = self.build(fixture(identifier))
            self.assertEqual(result.reference,
                             self.prefix + b'synthetic-directory/list/JP/ja/'
                             + str(identifier).encode() + b'.LZ')
            self.assertNotIn('synthetic', repr(result))
            self.assertNotIn('synthetic', repr(result.metadata()))
            for key in ('endpoint_authorized', 'catalog_downloaded_or_validated',
                        'record_schema_checked', 'native_browsing_verified',
                        'channel_language_eligibility_checked'):
                self.assertFalse(result.metadata()[key])

    def test_all_seven_reviewed_language_components(self):
        for code, component in enumerate((b'ja', b'en', b'de', b'fr', b'es', b'it', b'nl')):
            self.assertTrue(self.build(language_code=code).reference.endswith(b'/' + component + b'/0.LZ'))

    def test_raw_and_known_compression_inputs_have_same_reference(self):
        raw = fixture(123)
        expected = self.build(raw).reference
        for payload in (raw, encode_lz10(raw), encode_lz11(raw)):
            self.assertEqual(self.build(payload).reference, expected)

    def test_original_byte_concatenation_is_not_url_normalization_or_authorization(self):
        result = self.build(fixture(reference=b'../opaque ?\xff'))
        self.assertEqual(result.reference, self.prefix + b'../opaque ?\xff/list/JP/ja/0.LZ')
        self.assertFalse(result.metadata()['endpoint_authorized'])

    def test_capacity_boundary_rejects_truncation_instead_of_changing_request(self):
        tail = self.build(service_prefix=b'A').reference[1:]
        prefix = b'A' * (511 - len(tail))
        self.assertEqual(len(self.build(service_prefix=prefix).reference), 511)
        with self.assertRaisesRegex(ValueError, 'capacity'):
            self.build(service_prefix=prefix + b'A')

    def test_configuration_types_and_embedded_nuls_are_rejected_without_echo(self):
        for prefix in (b'', b'private\0marker', b'A' * 512, 'private-marker'):
            with self.subTest(kind=type(prefix)), self.assertRaises(ValueError) as caught:
                self.build(service_prefix=prefix)
            self.assertNotIn('private', str(caught.exception))
        for language in (-1, 7, True, '0'):
            with self.subTest(language=language), self.assertRaises(ValueError):
                self.build(language_code=language)

    def test_bad_csdata_cannot_produce_a_follow_on_reference(self):
        raw = bytearray(fixture()); raw[-1] ^= 1
        with self.assertRaisesRegex(ValueError, 'CRC'):
            self.build(bytes(raw))


class NintendoReferenceNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional Unicorn package unavailable')
        path = Path('private/nintendo/v1792/0001-0000003e.app')
        if not path.is_file():
            raise unittest.SkipTest('Private original HATJ v1792 executable unavailable')
        cls.source = path.read_bytes()

    def native(self, payload=None, prefix=b'https://synthetic.invalid/base/', language=0):
        from tools.verify_nintendo_references import verify_list_reference
        return verify_list_reference(self.source, payload if payload is not None else fixture(),
                                     service_prefix=prefix, language_code=language)

    def test_original_consumer_crc_append_formatter_and_country_language_resolvers_execute(self):
        result = self.native(fixture(4294967295))
        for field in ('native_crc_executed', 'native_reference_append_executed',
                      'native_decimal_formatter_executed', 'native_country_resolver_executed',
                      'native_language_resolver_executed', 'native_reference_matches_independent_plan',
                      'native_caller_and_manager_copies_executed',
                      'transport_callback_intercepted_before_execution',
                      'configuration_and_guards_verified'):
            self.assertTrue(result[field])
        self.assertEqual(result['counts']['logs_stubbed'], 0)
        self.assertFalse(result['catalog_download_or_records_verified'])
        self.assertFalse(result['channel_language_eligibility_checked'])
        self.assertFalse(result['network_transport_executed'])

    def test_original_language_table_and_unsigned_format_boundaries(self):
        for code in range(7):
            self.assertTrue(self.native(language=code)['native_reference_matches_independent_plan'])
        for identifier in (0, 1, 4294967295):
            self.assertTrue(self.native(fixture(identifier))['native_reference_matches_independent_plan'])

    def test_native_opaque_bytes_and_capacity_boundary_match(self):
        self.assertTrue(self.native(fixture(reference=b'../opaque ?\xff'))
                        ['native_reference_matches_independent_plan'])
        tail = build_japanese_list_reference(fixture(), service_prefix=b'A', language_code=0).reference[1:]
        result = self.native(prefix=b'A' * (511 - len(tail)))
        self.assertEqual(result['reference_bytes'], 511)


if __name__ == '__main__':
    unittest.main()
