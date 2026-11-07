"""Explicit setup metadata and private original-worker comparisons."""
from pathlib import Path
import unittest

from jwc24.cmoc_request_setup import ResourceSetup, project_request_setup


def inputs(**changes):
    value = dict(url='http://synthetic.invalid/first/3.ces', native_method_word=0,
                 configuration=ResourceSetup(20, b'wire-prefix', 1),
                 cached_prefix=bytes(range(12)), timestamp_present=True,
                 date_header_value=b'Sun, 01 Jan 2006 00:00:00 GMT',
                 appver_header_value=b'synthetic-appver', evidence_ref='synthetic only')
    value.update(changes)
    return value


def native_cases():
    result = []
    for secure in (False, True):
        for timestamp in (False, True):
            for cfg in (None, ResourceSetup(0, b'', 1),
                        ResourceSetup(20, bytes(range(64)), 0),
                        ResourceSetup(64, bytes(range(65)), 0xFFFFFFFF)):
                result.append(inputs(url=('https' if secure else 'http') + '://synthetic.invalid/first/3.ces',
                                     timestamp_present=timestamp, configuration=cfg))
    for cfg in (ResourceSetup(0, None, 0), ResourceSetup(1, b'x', 1)):
        result.append(inputs(configuration=cfg, appver_header_value=None))
    result.append(inputs(appver_header_value=b'A' * 63, date_header_value=b'D' * 75))
    return result


class RequestSetupTests(unittest.TestCase):
    def test_configured_capacity_prefix_bounds_and_zero_sizes(self):
        result = project_request_setup(**inputs(configuration=ResourceSetup(20, bytes(range(100)), 1),
                                               cached_prefix=bytes(range(100))))
        self.assertEqual(result.receive_capacity, 1108)
        self.assertEqual(result.retained_wire_prefix, bytes(range(64)))
        self.assertEqual(result.retained_cached_prefix, bytes(range(64)))
        self.assertTrue(result.decompression_requested)
        for prefix in (None, b''):
            zero = project_request_setup(**inputs(configuration=ResourceSetup(0, prefix, 1)))
            self.assertTrue(zero.configured)
            self.assertEqual(zero.receive_capacity, 1024)
            self.assertTrue(zero.decompression_requested)

    def test_unconfigured_branch_and_exact_url_byte_condition(self):
        for secure in (False, True):
            for timestamp in (False, True):
                result = project_request_setup(**inputs(
                    url=('https' if secure else 'http') + '://synthetic.invalid/first/3.bin',
                    timestamp_present=timestamp, configuration=None))
                self.assertEqual(result.secure_byte_predicate, secure)
                self.assertEqual(result.receive_capacity, 0x30000)
                self.assertFalse(result.decompression_requested)
                self.assertEqual([n for n, _ in result.requested_headers],
                                 (['If-Modified-Since'] if timestamp and not secure else []) + ['X-APPVER'])

    def test_null_appver_preserves_attempt_not_serialized_header(self):
        result = project_request_setup(**inputs(appver_header_value=None))
        self.assertEqual(result.requested_headers[-1], ('X-APPVER', None))

    def test_header_storage_boundaries_are_explicit_local_subset(self):
        result = project_request_setup(**inputs(appver_header_value=b'A' * 63,
                                               date_header_value=b'D' * 75))
        self.assertEqual(result.requested_headers,
                         (('If-Modified-Since', b'D' * 75), ('X-APPVER', b'A' * 63)))
        for changes in (dict(appver_header_value=b'A' * 64),
                        dict(date_header_value=b'D' * 76)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                project_request_setup(**inputs(**changes))

    def test_private_inputs_are_not_in_representation_or_metadata(self):
        marker = b'private-marker'
        cfg = ResourceSetup(20, marker, 1)
        result = project_request_setup(**inputs(configuration=cfg, cached_prefix=marker,
                                               appver_header_value=marker, evidence_ref=marker.decode()))
        self.assertNotIn(marker.decode(), repr(result))
        self.assertNotIn(marker.decode(), repr(cfg))
        self.assertNotIn(marker.decode(), str(result.metadata()))
        self.assertFalse(result.metadata()['cryptographic_initialization_verified'])

    def test_invalid_metadata_rejects_without_echoing_values(self):
        for changes in (dict(url='http://x/\nprivate-marker'), dict(native_method_word=True),
                        dict(native_method_word=3), dict(configuration={}),
                        dict(cached_prefix='private-marker'), dict(timestamp_present=1),
                        dict(date_header_value=None), dict(appver_header_value=b'private-marker\r\n'),
                        dict(evidence_ref='')):
            with self.subTest(changes=changes), self.assertRaises(ValueError) as caught:
                project_request_setup(**inputs(**changes))
            self.assertNotIn('private-marker', str(caught.exception))
        for args in ((65, b'', 1), (True, None, 0), (0, b'x' * 4097, 1), (0, None, -1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                ResourceSetup(*args)


class RequestSetupNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('private/cmoc/v512/0001-0000000c.app')
        if not path.is_file():
            raise unittest.SkipTest('Private Japanese CMOC v512 executable unavailable')
        try:
            import capstone  # noqa: F401
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional native verification dependencies unavailable')
        cls.source = path.read_bytes()

    def test_actual_cached_worker_configured_path_and_sdk_outer_constructor(self):
        from tools.verify_cmoc_request_setup import verify_request_setup
        for i, value in enumerate(native_cases()):
            with self.subTest(case=i):
                report = verify_request_setup(self.source, **value)
                self.assertTrue(report['complete_cached_worker_and_setup_executed'])
                self.assertTrue(report['complete_sdk_outer_constructor_executed'])
                self.assertTrue(report['input_and_stack_guards_verified'])
                self.assertEqual(report['counts']['worker_calls'], 1)
                self.assertEqual(report['counts']['sdk_constructor_calls'], 1)
                self.assertEqual(report['counts']['configured_constructor_calls'], int(value['configuration'] is not None))
                self.assertFalse(report['cryptographic_initialization_verified'])


if __name__ == '__main__':
    unittest.main()
