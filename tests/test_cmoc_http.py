"""Synthetic SDK HTTP headers; no remote requests or genuine client records."""
from pathlib import Path
import unittest

from jwc24.cmoc import CMOCFormatError, CMOCUnsupportedFormat
from jwc24.cmoc_http import decode_completion_transport, inspect_first_data_http_completion
from jwc24.cmoc_startup import encode_first_data_record
from tests.test_cmoc_response_gate import header


def transport(**changes):
    result = dict(status_field=200, response_ready=True, headers=())
    result.update(changes)
    return result


def native_cases():
    cases = [('result-' + str(index), transport(headers=((b'X-RESULT', value),)))
             for index, value in enumerate((b'', b'0', b'001', b'0100', b'100', b'9999',
                                            b'abc', b'123tail', b'  100', b'\t100', b'+100',
                                            b'-100', b'+', b'-', b'-0', b'0x64', b'12 3'))]
    cases += [
        ('absent-result', transport()),
        ('lowercase', transport(headers=((b'x-result', b'100'),))),
        ('mixed-case', transport(headers=((b'X-Result', b'100'),))),
        ('duplicate-first-high', transport(headers=((b'X-RESULT', b'100'), (b'X-RESULT', b'001')))),
        ('duplicate-first-low', transport(headers=((b'X-RESULT', b'001'), (b'x-result', b'100')))),
        ('missing-response', transport(status_field=None, headers=((b'X-RESULT', b'100'),))),
        ('response-not-ready', transport(response_ready=False, headers=((b'X-RESULT', b'100'),))),
        ('explicit-status-error', transport(status_field=503)),
        ('explicit-negative-status', transport(status_field=-1)),
    ]
    for index, value in enumerate((b'', b'example.invalid', b'  example.invalid  ', b'\texample.invalid\t')):
        cases.append(('host-' + str(index), transport(headers=((b'X-MC-HOST', value),))))
    cases.append(('host-lowercase', transport(headers=((b'x-mc-host', b'example.invalid'),))))
    cases.append(('host-duplicate', transport(headers=((b'X-MC-HOST', b'first.invalid'),
                                                       (b'x-mc-host', b'second.invalid')))))
    return cases


class CMOCHttpTests(unittest.TestCase):
    def test_native_three_character_decimal_field_width_and_initialized_zero(self):
        for raw, expected in ((b'0100', 10), (b'100', 100), (b'9999', 999), (b'abc', 0),
                              (b'-100', -10), (b'+100', 10), (b'\t100tail', 100), (b'0x64', 0)):
            with self.subTest(raw=raw):
                result = decode_completion_transport(**transport(headers=((b'X-RESULT', raw),)))
                self.assertEqual(result.x_result, expected)
        self.assertEqual(decode_completion_transport(**transport()).x_result, 0)

    def test_case_insensitive_first_match_and_exact_sdk_host_whitespace(self):
        result = decode_completion_transport(**transport(headers=(
            (b'x-result', b'001'), (b'X-RESULT', b'100'),
            (b'X-MC-HOST', b'  example.invalid  '))))
        self.assertEqual((result.x_result, result.x_result_fields), (1, 2))
        self.assertEqual(result.host_override, b'example.invalid  ')
        self.assertNotIn('example.invalid', repr(result))
        self.assertNotIn('example.invalid', str(result.metadata()))

    def test_unavailable_and_not_ready_status_do_not_infer_transport(self):
        for kwargs in (transport(status_field=None), transport(response_ready=False)):
            result = decode_completion_transport(**kwargs)
            self.assertEqual((result.http_status, result.x_result, result.host_override), (-1, 0, None))
            self.assertFalse(result.metadata()['http_wire_status_line_parsing_verified'])

    def test_actual_header_conversion_drives_gate_and_existing_fd_decoder(self):
        record = encode_first_data_record(word_4=12, byte_8=2, byte_9=3, u16_a=4,
                                         evidence_ref='synthetic HTTP handoff fixture')
        args = dict(expected_request=header(), response_flags=0x20, limit_byte_2=4, learned_byte_3=255)
        observed, result = inspect_first_data_http_completion(
            header() + record, **transport(headers=((b'X-RESULT', b'0100'),)), **args)
        self.assertEqual(observed.x_result, 10)
        self.assertTrue(result.gate.header_gate_passed)
        self.assertEqual(result.response.record.word_4, 12)
        with self.assertRaises(CMOCFormatError):
            inspect_first_data_http_completion(header() + record,
                                               **transport(headers=((b'X-RESULT', b'100'),)), **args)
        for kwargs in (transport(status_field=None), transport(response_ready=False)):
            with self.assertRaises(CMOCFormatError):
                inspect_first_data_http_completion(header() + record, **kwargs, **args)
        for fields in (((b'X-RESULT', b'0'), (b'x-result', b'0')),
                       ((b'X-MC-HOST', b'example.invalid'),)):
            with self.assertRaises(CMOCUnsupportedFormat):
                inspect_first_data_http_completion(header() + record, **transport(headers=fields), **args)

    def test_unreviewed_header_forms_and_bounds_reject_without_echo(self):
        for fields in (((b'X-RESULT ', b'0'),), ((b'X-RESULT', b'private\r\nmarker'),),
                       ((b'X-RESULT', b'\x80'),), ((b'X-RESULT', b'0' * 257),),
                       ((b'Other', b'x' * 250),) * 5):
            with self.assertRaises(ValueError) as caught:
                decode_completion_transport(**transport(headers=fields))
            self.assertNotIn('private', str(caught.exception))


class CMOCHttpNativeTests(unittest.TestCase):
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

    def test_actual_sdk_lookup_status_getter_and_scanf_boundaries(self):
        from tools.verify_cmoc_http import verify_http_transport
        for label, kwargs in native_cases():
            with self.subTest(case=label):
                report = verify_http_transport(self.source, **kwargs)
                self.assertTrue(report['input_heap_and_stack_guards_verified'])
                self.assertFalse(report['sdk_header_lookup_and_scanf_stubbed'])
                self.assertFalse(report['authentication_or_startup_verified'])


if __name__ == '__main__':
    unittest.main()
