"""Receive setup/callback composition and actual original buffer geometry."""
from dataclasses import replace
from pathlib import Path
import unittest

from jwc24.cmoc_callback import CallbackState, process_body_event
from jwc24.cmoc_receive import (ConfiguredReceiveLayout, check_configured_receive_layout,
                                check_transform_extent)
from jwc24.cmoc_request_setup import ResourceSetup, project_request_setup


def setup(span=20, prefix=12, configured=True):
    return project_request_setup(url='http://example.test/first/value', native_method_word=0,
        configuration=ResourceSetup(span, b'P' * prefix, 1) if configured else None,
        cached_prefix=b'C' * 12, timestamp_present=False, date_header_value=None,
        appver_header_value=None, evidence_ref='synthetic receive geometry test')


class ReceiveGeometryTests(unittest.TestCase):
    def test_all_setup_sizes_keep_projection_distinct_from_storage_acceptance(self):
        fits = rejects = 0
        for span in range(65):
            for prefix in range(65):
                projected = setup(span, prefix)
                if span + prefix > 64:
                    with self.assertRaises(ValueError):
                        check_configured_receive_layout(projected, resolved_hash_span_size=span)
                    self.assertGreater(projected.receive_capacity, 0x440)
                    rejects += 1
                else:
                    checked = check_configured_receive_layout(projected, resolved_hash_span_size=span)
                    self.assertEqual(checked.advertised_capacity, projected.receive_capacity)
                    self.assertEqual(checked.transform_offset, span + prefix)
                    fits += 1
        self.assertEqual((fits, rejects), (2145, 2080))

    def test_every_endpoint_composes_with_existing_callback_and_actual_backing(self):
        for span, prefix in ((0, 0), (20, 12), (20, 44), (64, 0), (0, 64)):
            projected = setup(span, prefix)
            layout = check_configured_receive_layout(projected, resolved_hash_span_size=span)
            state = CallbackState(0x0C, projected.retained_wire_prefix, b'', b'', span, False)
            for payload in range(1025):
                endpoint = layout.transform_offset + payload
                extent = check_transform_extent(layout, receive_end_offset=endpoint,
                                                 backing_bytes=layout.advertised_capacity)
                backing = projected.retained_wire_prefix + bytes(extent.required_backing_end - prefix)
                result = process_body_event(state, wire_storage=backing, receive_end_offset=endpoint,
                                            decoded_chunk=b'', raw_body=None)
                self.assertEqual(result.padded_transform_size, extent.padded_transform_bytes)
                if payload % 16:
                    self.assertGreater(extent.required_backing_end, endpoint)
                    with self.assertRaises(ValueError):
                        check_transform_extent(layout, receive_end_offset=endpoint, backing_bytes=endpoint)

    def test_partial_header_or_over_capacity_never_wraps_or_clamps(self):
        layout = check_configured_receive_layout(setup(), resolved_hash_span_size=20)
        for endpoint in (0, 15, 16, 17, 31, layout.advertised_capacity + 1):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                check_transform_extent(layout, receive_end_offset=endpoint, backing_bytes=0x440)
        zero = check_transform_extent(layout, receive_end_offset=32, backing_bytes=32)
        self.assertEqual((zero.received_payload_bytes, zero.padded_transform_bytes), (0, 0))
        self.assertEqual(zero.required_backing_end, 32)

    def test_explicit_types_capacity_and_retained_prefix_must_agree(self):
        projected = setup()
        for changed, span in ((replace(projected, receive_capacity=0x440), 20),
                              (replace(projected, retained_wire_prefix='private-marker'), 20),
                              (setup(configured=False), 0), (projected, True),
                              (projected, 'private-marker'), (projected, -1), (projected, 65)):
            with self.assertRaises(ValueError) as caught:
                check_configured_receive_layout(changed, resolved_hash_span_size=span)
            self.assertNotIn('private-marker', str(caught.exception))
        for values in ((20, 12, 31, 1056), (64, 1, 65, 1089), (False, 0, 0, 1024)):
            with self.assertRaises(ValueError):
                ConfiguredReceiveLayout(*values)
        layout = check_configured_receive_layout(projected, resolved_hash_span_size=20)
        for kwargs in (dict(receive_end_offset=True, backing_bytes=64),
                       dict(receive_end_offset=32, backing_bytes=0x441),
                       dict(receive_end_offset=33, backing_bytes=47)):
            with self.assertRaises(ValueError):
                check_transform_extent(layout, **kwargs)


class ReceiveGeometryNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'private/cmoc/v512/0001-0000000c.app'
        if not path.is_file():
            raise unittest.SkipTest('Optional private Japanese CMOC v512 executable unavailable')
        try:
            import capstone  # noqa: F401
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional native verification dependencies unavailable')
        cls.source = path.read_bytes()

    def test_original_storage_resets_capacity_and_rounding_with_adjacent_guards(self):
        from tools.verify_cmoc_receive import verify_receive_geometry
        result = verify_receive_geometry(self.source)
        self.assertEqual(result['original_storage_resets'], 2)
        self.assertEqual((result['wire_storage_bytes'], result['intermediate_storage_bytes']),
                         (0x440, 0x400))
        self.assertEqual(result['original_capacity_cases'], 4225)
        self.assertEqual(result['capacity_fits_storage_cases'], 2145)
        self.assertEqual(result['capacity_exceeds_storage_cases'], 2080)
        self.assertEqual(result['original_rounding_cases'], 29575)
        self.assertEqual(result['original_partial_header_cases'], 16490)
        self.assertTrue(result['object_and_stack_guards_unchanged'])
        self.assertFalse(result['original_helpers_or_memset_stubbed'])
        self.assertFalse(result['actual_live_resource_sizes_verified'])
        self.assertFalse(result['sdk_chunking_or_crypto_verified'])


if __name__ == '__main__':
    unittest.main()
