"""Synthetic language/catalog handoffs; no production content or requests."""
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from jwc24.forecast import encode_lz10
from jwc24.lz11 import encode_lz11
from jwc24.nintendo_listdata import MAX_LIST_BYTES, ListDataFormatError, inspect_listdata
from jwc24.nintendo_load import (NintendoLoadError, inspect_japanese_list_download,
                                 plan_japanese_list_load)
from tests.test_nintendo_csdata import synthetic_csdata, with_crc
from tests.test_nintendo_listdata import synthetic_listdata


PREFIX = b'https://synthetic.invalid/base/'


def csdata(languages, *, tail=255):
    raw = bytearray(synthetic_csdata(reference=b'synthetic-list'))
    raw[0x18:0x28] = bytes(languages) + bytes([tail]) * (16 - len(languages))
    return with_crc(raw)


class NintendoLoadTests(unittest.TestCase):
    def test_language_prefix_stops_at_first_unreviewed_entry_and_preserves_duplicates(self):
        plan = plan_japanese_list_load(csdata([0, 0, 6, 7, 1]), service_prefix=PREFIX, language_code=6)
        self.assertEqual(plan.accepted_language_entries, (0, 0, 6))
        self.assertTrue(plan.language_eligible)
        self.assertTrue(plan.reference.reference.endswith(b'/list/JP/nl/0.LZ'))
        ignored = plan_japanese_list_load(csdata([0, 0, 6, 7, 1]), service_prefix=PREFIX, language_code=1)
        self.assertFalse(ignored.language_eligible)
        self.assertIsNone(ignored.reference)
        self.assertEqual(len(plan_japanese_list_load(csdata([0] * 16), service_prefix=PREFIX,
                                                    language_code=0).accepted_language_entries), 16)

    def test_empty_prefix_and_unknown_configured_language_prepare_no_request(self):
        for languages, selected in (([], 0), ([0], 7), ([0, 1, 2, 3, 4, 5, 6], 255)):
            plan = plan_japanese_list_load(csdata(languages), service_prefix=PREFIX, language_code=selected)
            self.assertFalse(plan.language_eligible)
            self.assertIsNone(plan.reference)
            self.assertTrue(plan.metadata()['channel_language_eligibility_checked'])
            self.assertFalse(plan.metadata()['catalog_downloaded'])

    def test_handoff_keeps_actual_records_across_raw_lz10_and_lz11(self):
        header, body = csdata([0, 1]), synthetic_listdata()
        for wrap in (lambda value: value, encode_lz10, encode_lz11):
            result = inspect_japanese_list_download(wrap(header), wrap(body),
                                                     service_prefix=PREFIX, language_code=0)
            self.assertTrue(result.plan.language_eligible)
            self.assertEqual([row.software_index for row in result.listdata.linked_rows], [1, 0])
            self.assertEqual(result.listdata.software_rows[0].title, 'Synthetic title \u65e5\u672c\u8a9e \U0001F30F')
            for key in ('download_reference_or_response_origin_verified',
                        'authentication_or_freshness_verified', 'native_publication_or_browsing_verified'):
                self.assertFalse(result.metadata()[key])
            self.assertNotIn('Synthetic title', repr(result))
            self.assertNotIn('synthetic.invalid', repr(result))

    def test_failed_language_gate_never_becomes_an_empty_or_unchecked_catalog(self):
        with patch('jwc24.nintendo_load.inspect_listdata', side_effect=AssertionError('body must not be parsed')):
            with self.assertRaisesRegex(NintendoLoadError, 'language'):
                inspect_japanese_list_download(csdata([0]), b'not list data',
                                                service_prefix=PREFIX, language_code=1)

    def test_existing_strict_record_policy_rejects_raw_allocation_padding_and_other_versions(self):
        raw = synthetic_listdata()
        for bad in (raw + b'\xA5' * 16, raw[:2] + b'\x07' + raw[3:]):
            with self.assertRaises(ListDataFormatError):
                inspect_japanese_list_download(csdata([0]), bad, service_prefix=PREFIX, language_code=0)

    def test_invalid_csdata_cannot_prepare_a_follow_on_load(self):
        raw = bytearray(csdata([0])); raw[-1] ^= 1
        with self.assertRaisesRegex(ValueError, 'CRC'):
            plan_japanese_list_load(bytes(raw), service_prefix=PREFIX, language_code=0)

    def test_explicit_configuration_bounds_are_sanitized(self):
        for language in (True, -1, 256, 'private-marker'):
            with self.assertRaises(ValueError) as caught:
                plan_japanese_list_load(csdata([0]), service_prefix=PREFIX, language_code=language)
            self.assertNotIn('private-marker', str(caught.exception))
        for prefix in (b'', b'private\0marker', b'A' * 512, 'private-marker'):
            with self.assertRaises(ValueError) as caught:
                plan_japanese_list_load(csdata([0]), service_prefix=prefix, language_code=0)
            self.assertNotIn('private', str(caught.exception))

    def test_native_verifier_refuses_unverified_software_before_optional_emulation(self):
        from tools.verify_nintendo_load import verify_nintendo_load
        with self.assertRaisesRegex(ValueError, 'fingerprint') as caught:
            verify_nintendo_load(b'private-marker', csdata([0]), None,
                                  language_code=0, prior_load_result=0)
        self.assertNotIn('private-marker', str(caught.exception))


class NintendoLoadNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('private/nintendo/v1792/0001-0000003e.app')
        if not path.is_file():
            raise unittest.SkipTest('Private original Japanese HATJ v1792 executable unavailable')
        try:
            import capstone  # noqa: F401
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional native verification dependency unavailable')
        cls.source = path.read_bytes()

    def run_native(self, languages, selected, payload=None, prior=0):
        from tools.verify_nintendo_load import verify_nintendo_load
        return verify_nintendo_load(self.source, csdata(languages), payload,
                                     language_code=selected, prior_load_result=prior)

    def test_actual_language_loop_uses_prefix_and_suppresses_download_for_absent_language(self):
        for languages in ([], [0], [6], [0, 1, 2, 3, 4, 5, 6], [0] * 16, [0, 7, 1]):
            for selected in (0, 1, 6, 7, 255):
                with self.subTest(languages=languages, selected=selected):
                    result = self.run_native(languages, selected)
                    self.assertTrue(result['native_language_gate_executed'])
                    self.assertFalse(result['native_install_slice_executed'])
                    self.assertEqual(result['native_ineligible_language_published_csdata_only'],
                                     not result['language_eligible'])
                    self.assertTrue(result['input_output_context_and_stack_guards_verified'])
                    self.assertEqual(result['counts']['temporary_frees'], 0)

    def test_actual_retail_allocation_raw_copy_and_lz_install_publish_only_after_validation(self):
        body = synthetic_listdata()
        for wrap, prior in ((lambda value: value, 0), (encode_lz10, 1), (encode_lz11, 0)):
            with self.subTest(prior=prior):
                result = self.run_native([0], 0, wrap(body), prior)
                self.assertTrue(result['retail_capacity_callsite_verified'])
                self.assertTrue(result['retail_capacity_used'])
                self.assertEqual(result['allocation_bytes'], MAX_LIST_BYTES)
                self.assertTrue(result['native_install_slice_executed'])
                self.assertEqual(result['native_validator_result'], 0)
                self.assertTrue(result['native_install_publication_pair_updated'])
                self.assertTrue(result['native_constructor_global_pointer_assigned_before_validation'])
                self.assertTrue(result['independent_record_subset_accepted'])
                self.assertFalse(result['original_copy_decompressor_constructor_validator_stubbed'])
                self.assertEqual(result['counts']['temporary_frees'], 1)
                self.assertTrue(result['input_output_context_and_stack_guards_verified'])

    def test_invalid_native_record_keeps_publication_pair_but_constructor_global_still_changes(self):
        body = bytearray(synthetic_listdata())
        offset = inspect_listdata(bytes(body)).tables[5].offset
        body[offset + 0x0A] = 11
        result = self.run_native([0], 0, bytes(body))
        self.assertNotEqual(result['native_validator_result'], 0)
        self.assertFalse(result['native_install_publication_pair_updated'])
        self.assertTrue(result['native_constructor_global_pointer_assigned_before_validation'])
        self.assertFalse(result['independent_record_subset_accepted'])
        self.assertEqual(result['counts']['temporary_frees'], 1)
        self.assertEqual(result['counts']['error_boundaries'], 1)
        self.assertEqual(result['counts']['scheduler_boundaries'], 0)

    def test_native_version_acceptance_does_not_override_stricter_supported_backend(self):
        body = bytearray(synthetic_listdata()); body[2] = 7
        result = self.run_native([0], 0, encode_lz10(bytes(body)))
        self.assertEqual(result['native_validator_result'], 0)
        self.assertTrue(result['native_install_publication_pair_updated'])
        self.assertFalse(result['independent_record_subset_accepted'])
        self.assertFalse(result['authentication_freshness_or_browsing_verified'])


if __name__ == '__main__':
    unittest.main()
