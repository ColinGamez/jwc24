"""Original request construction uses explicit synthetic state only."""
from pathlib import Path
import struct
import unittest

from jwc24.cmoc_request import build_first_data_request, parse_first_data_target
from jwc24.cmoc_http import inspect_first_data_http_completion
from jwc24.cmoc_startup import encode_first_data_record


def inputs(**changes):
    value = dict(word_4=12, word_8=0x12345678, byte_2=4, byte_3=5,
                 opaque_header_tail=bytes(range(20)), configuration_2c_predicate=False,
                 evidence_ref='synthetic-only request fixture')
    value.update(changes)
    return value


def native_cases():
    cases = []
    for value in (0, 1, 99, 100, 0x7FFFFFFF, 0xFFFFFFFF):
        for predicate in (False, True):
            cases.append(inputs(word_4=value, configuration_2c_predicate=predicate))
    for value in (0, 1, 0x7FFFFFFF, 0xFFFFFFFF):
        cases.append(inputs(word_8=value))
    for byte_2, byte_3 in ((0, 0), (0, 255), (255, 0), (255, 255)):
        cases.append(inputs(byte_2=byte_2, byte_3=byte_3))
    for tail in (bytes(20), b'\xFF' * 20, bytes(range(200, 220))):
        cases.append(inputs(opaque_header_tail=tail))
    return cases


class CMOCRequestTests(unittest.TestCase):
    def test_backend_target_decoder_preserves_canonical_native_numeric_field_and_selector(self):
        for suffix, predicate in (('.ces', False), ('.bin', True)):
            for value in (0, 1, 0xFFFFFFFF):
                result = parse_first_data_target(f'/first/{value}{suffix}')
                self.assertEqual((result.word_4, result.configuration_2c_predicate), (value, predicate))
        for target in ('/first/01.ces', '/first/-1.bin', '/first/4294967296.ces',
                       '/first/1.CES', '/first/1.bin?x=1', '/first/%31.ces',
                       'http://private-marker/first/1.bin', '/first/1.ces/extra',
                       '/first/1.ces\n', b'/first/1.ces'):
            with self.subTest(target=target), self.assertRaises(ValueError) as caught:
                parse_first_data_target(target)
            self.assertNotIn('private-marker', str(caught.exception))

    def test_fd_uses_word4_unsigned_decimal_and_observed_suffix_selection(self):
        for predicate, suffix in ((False, '.ces'), (True, '.bin')):
            result = build_first_data_request(origin='http://synthetic.invalid/',
                                              **inputs(word_4=0xFFFFFFFF,
                                                       configuration_2c_predicate=predicate))
            self.assertEqual(result.url, 'http://synthetic.invalid/first/4294967295' + suffix)
            self.assertEqual((result.family_word, result.method_word), (0, 0))
            self.assertEqual(result.cached_header,
                             struct.pack('>HBBII', 0x4644, 4, 5, 0xFFFFFFFF, 0x12345678) + bytes(range(20)))
            self.assertNotIn('synthetic.invalid', repr(result))
            self.assertFalse(result.metadata()['request_body_serialization_verified'])
            self.assertFalse(result.metadata()['transport_or_authentication_verified'])

    def test_supplied_header_tail_is_preserved_without_creating_a_zero_default(self):
        for tail in (bytes(20), b'\xFF' * 20, bytes(range(20))):
            result = build_first_data_request(origin='http://synthetic.invalid',
                                              **inputs(opaque_header_tail=tail))
            self.assertEqual(result.cached_header[12:], tail)
        with self.assertRaises(TypeError):
            value = inputs()
            del value['opaque_header_tail']
            build_first_data_request(origin='http://synthetic.invalid', **value)

    def test_produced_correlation_header_drives_existing_http_gate_and_fd_record_decoder(self):
        request = build_first_data_request(origin='http://synthetic.invalid', **inputs())
        record = encode_first_data_record(word_4=34, byte_8=1, byte_9=2, u16_a=3,
                                         evidence_ref='synthetic record fixture')
        _, result = inspect_first_data_http_completion(
            request.cached_header + record, status_field=200, response_ready=True,
            headers=((b'X-RESULT', b'000'),), expected_request=request.cached_header,
            response_flags=0x20, limit_byte_2=4, learned_byte_3=255)
        self.assertTrue(result.gate.header_gate_passed)
        self.assertEqual(result.response.record.word_4, 34)
        self.assertFalse(result.metadata()['authentication_or_startup_verified'])

    def test_unsupported_widths_and_missing_opaque_state_reject_without_echo(self):
        for key, value in (('word_4', -1), ('word_8', 1 << 32), ('word_4', True),
                            ('byte_2', 256), ('byte_3', -1), ('opaque_header_tail', b'private-marker'),
                            ('configuration_2c_predicate', 1), ('evidence_ref', '')):
            with self.subTest(key=key), self.assertRaises(ValueError) as caught:
                build_first_data_request(origin='http://synthetic.invalid', **inputs(**{key: value}))
            self.assertNotIn('private-marker', str(caught.exception))

    def test_origin_is_explicit_bounded_local_policy_not_a_recovered_service_capture(self):
        for origin in ('http://user:private-marker@x', 'http://x/path', 'http://x?',
                       'http://x/#', 'file:///private-marker', 'http://x;private-marker',
                       'http://x:0', 'http://x:99999', 'http://x\n', 'http://x\\secret',
                       'http://' + 'x' * 95):
            with self.subTest(origin=origin), self.assertRaises(ValueError) as caught:
                build_first_data_request(origin=origin, **inputs())
            self.assertNotIn('private-marker', str(caught.exception))


class CMOCRequestNativeTests(unittest.TestCase):
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

    def test_complete_request_constructor_and_actual_printf_and_configuration_branches(self):
        from tools.verify_cmoc_request import verify_first_data_request
        for index, value in enumerate(native_cases()):
            with self.subTest(case=index):
                report = verify_first_data_request(self.source, **value)
                self.assertTrue(report['complete_request_seed_and_descriptor_constructor_executed'])
                self.assertTrue(report['input_descriptor_and_stack_guards_verified'])
                self.assertTrue(report['opaque_header_tail_preserved_unchanged'])
                self.assertEqual(report['counts']['native_snprintf_calls'], 3)
                self.assertEqual(report['counts']['native_configuration_predicate_calls'], 1)
                self.assertFalse(report['native_printf_header_copy_suffix_or_config_predicate_stubbed'])


if __name__ == '__main__':
    unittest.main()
