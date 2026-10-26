"""Explicit synthetic completion inputs; no genuine host, Mii or service data."""
from pathlib import Path
import struct
import unittest

from jwc24.cmoc import CMOCFormatError
from jwc24.cmoc_response_gate import evaluate_response_gate, inspect_first_data_completion
from jwc24.cmoc_startup import encode_first_data_record


def header(byte_2=4, byte_3=5):
    return struct.pack('>HBBII20x', 0x4644, byte_2, byte_3, 0x11223344, 0x55667788)


def inputs(**changes):
    result = dict(expected_request=header(), http_status=200, x_result=0,
                  response_flags=0x20, limit_byte_2=4, learned_byte_3=255)
    result.update(changes)
    return result


def native_cases():
    cases = [('flags-' + str(flags), header(), inputs(response_flags=flags)) for flags in range(256)]
    for status in (-1, 0, 299, 300, 503, 0x7FFFFFFF):
        cases.append(('http-' + str(status), header(), inputs(http_status=status)))
    for result in (-1, 99, 100, 999, 0x7FFFFFFF):
        cases.append(('result-' + str(result), header(), inputs(x_result=result)))
    for size in (0, 1, 31):
        cases.append(('short-' + str(size), header()[:size], inputs()))
    for offset in (0, 4, 8):
        raw = bytearray(header())
        raw[offset] ^= 1
        cases.append(('correlation-' + str(offset), bytes(raw), inputs()))
    for byte, limit in ((0, 0), (1, 0), (4, 3), (254, 254), (255, 255)):
        cases.append(('byte2-' + str(byte) + '-' + str(limit), header(byte_2=byte), inputs(limit_byte_2=limit)))
    for received, prior in ((5, 5), (6, 5), (255, 255), (0, 255), (255, 0)):
        cases.append(('byte3-' + str(received) + '-' + str(prior), header(byte_3=received), inputs(learned_byte_3=prior)))
    cases.append(('missing-request', b'', inputs(expected_request=None, http_status=503,
                                               x_result=999, response_flags=255)))
    return cases


class CMOCResponseGateTests(unittest.TestCase):
    def test_zero_completion_is_not_a_header_pass_when_request_or_body_is_missing(self):
        for kwargs in (inputs(expected_request=None), inputs(response_flags=0)):
            gate = evaluate_response_gate(b'', **kwargs)
            self.assertEqual(gate.completion_code, 0)
            self.assertFalse(gate.header_gate_passed)
            self.assertFalse(gate.body_header_checked)
            self.assertEqual(gate.next_byte_3, 255)
        self.assertFalse(evaluate_response_gate(b'', **inputs(expected_request=None)).http_status_checked)

    def test_observed_order_codes_and_state_learning(self):
        self.assertEqual(evaluate_response_gate(header(), **inputs(http_status=503, x_result=999)).completion_code,
                         503 + 0x3EFD0)
        self.assertEqual(evaluate_response_gate(header(), **inputs(x_result=100, response_flags=255)).completion_code,
                         100 + 0x3EBE8)
        self.assertEqual(evaluate_response_gate(header(), **inputs(response_flags=0x70)).completion_code, 0x3D8C5)
        self.assertEqual(evaluate_response_gate(header(), **inputs(response_flags=0x30)).completion_code, 0x3D929)
        learned = evaluate_response_gate(header(), **inputs())
        self.assertTrue(learned.header_gate_passed)
        self.assertEqual(learned.next_byte_3, 5)
        self.assertTrue(learned.byte_3_changed)
        rejected = evaluate_response_gate(header(byte_3=6), **inputs(learned_byte_3=5))
        self.assertEqual(rejected.completion_code, 0x3D8C8)
        self.assertEqual(rejected.next_byte_3, 5)

    def test_fd_handoff_requires_gate_then_existing_record_and_framing_checks(self):
        record = encode_first_data_record(word_4=0x12345678, byte_8=2, byte_9=3,
                                         u16_a=0x4567, evidence_ref='explicit synthetic gate fixture')
        result = inspect_first_data_completion(header() + record, **inputs())
        self.assertTrue(result.gate.header_gate_passed)
        self.assertEqual(result.response.record.word_4, 0x12345678)
        self.assertTrue(result.metadata()['header_byte_2_and_3_checks_executed'])
        self.assertFalse(result.metadata()['authentication_or_startup_verified'])
        for raw, kwargs in ((header() + record, inputs(response_flags=0)),
                            (header() + record, inputs(expected_request=None)),
                            (header() + record[:8], inputs()), (header(), inputs())):
            with self.assertRaises(CMOCFormatError):
                inspect_first_data_completion(raw, **kwargs)

    def test_width_and_type_failures_are_sanitized(self):
        for field, value in (('expected_request', b'private-marker'), ('http_status', True),
                             ('x_result', 1 << 31), ('response_flags', 256),
                             ('limit_byte_2', -1), ('learned_byte_3', 'private-marker')):
            with self.subTest(field=field), self.assertRaises(ValueError) as caught:
                evaluate_response_gate(header(), **inputs(**{field: value}))
            self.assertNotIn('private-marker', str(caught.exception))


class CMOCResponseGateNativeTests(unittest.TestCase):
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

    def test_full_handler_all_flag_bytes_and_transport_header_state_boundaries(self):
        from tools.verify_cmoc_response_gate import verify_response_gate
        for label, raw, kwargs in native_cases():
            with self.subTest(case=label):
                report = verify_response_gate(self.source, raw, **kwargs)
                self.assertTrue(report['full_completion_handler_executed'])
                self.assertTrue(report['input_state_and_stack_guards_verified'])
                self.assertFalse(report['header_branches_or_state_updates_stubbed'])
                self.assertFalse(report['authentication_or_startup_verified'])


if __name__ == '__main__':
    unittest.main()
