from pathlib import Path
import struct
import unittest

from tools.verify_demae_postal_pipeline import verify, verify_request_reset


def row(code, text):
    return struct.pack('>I', code)+b''.join(t.encode('utf-16-be')+b'\0\0' for t in text)


class NativePostalPipelineTests(unittest.TestCase):
    def check(self, raw, query, *, lz11=False, cancelled=False, **options):
        path = Path(__file__).resolve().parents[1]/'private/demae/v2/main.decompressed.dol'
        if not path.is_file():
            self.skipTest('Private helper executable unavailable')
        from Crypto.Cipher import AES
        from jwc24.forecast import encode_lz10_literal
        from jwc24.lz11 import encode_lz11
        compressed = (encode_lz11 if lz11 else encode_lz10_literal)(raw)
        plain = b'zpcd\x10'+bytes(11)+compressed
        plain += bytes((-len(plain)) % 16)
        key, iv = bytes(range(32)), bytes(range(16))
        encrypted = AES.new(key, AES.MODE_CBC, iv).encrypt(plain)
        report = verify(path.read_bytes(), key, iv, encrypted, query, cancelled=cancelled, **options)
        self.assertTrue(report['cleanup_verified'])
        return report

    def test_both_compression_types_and_all_lookup_outcomes(self):
        raw = row(3770800, ('alternative', '', ''))+row(3770813, ('群馬県', 'test municipality', 'test town'))
        for lz11 in (False, True):
            for query, kind in ((3770813, 'exact'), (3770899, 'alternative'), (9999999, 'not_found')):
                with self.subTest(lz11=lz11, kind=kind):
                    self.assertEqual(self.check(raw, query, lz11=lz11)['result_kind'], kind)

    def test_duplicate_fallback_and_exact_source_order(self):
        for code, query in ((3770800, 3770813), (3770813, 3770813)):
            self.check(row(code, ('first', '', ''))+row(code, ('last', '', '')), query, lz11=True)

    def test_cancellation_between_native_stages(self):
        report = self.check(row(1, ('test', '', '')), 1, cancelled=True)
        self.assertEqual(report['native_status'], 1)
        self.assertIsNone(report['result_kind'])

    def test_utf16_capacities_and_zero_bucket(self):
        text = ('県'*31, '\U0001f363'*15+'a', '町'*63)
        self.assertEqual(self.check(row(0, text), 99, lz11=True)['result_kind'], 'alternative')
        self.assertEqual(self.check(row(0, text), 0)['result_kind'], 'exact')

    def test_stage_read_write_failures_stop_processing(self):
        for lz11 in (False, True):
            for fault in ('decrypt_read', 'decrypt_write', 'unpack_read', 'unpack_write', 'final_read'):
                with self.subTest(lz11=lz11, fault=fault):
                    report = self.check(row(1, ('test', '', '')), 1, lz11=lz11, fault=fault)
                    self.assertEqual(report['native_status'], 0x15)
                    self.assertEqual(report['fault_exercised'], fault)
                    self.assertFalse(report['native_ready_flag'])
                    self.assertFalse(report['new_result_published'])

    def test_prior_result_survives_failure_and_cancellation(self):
        for options in ({'cancelled': True}, *({'fault': fault} for fault in
                        ('decrypt_read', 'decrypt_write', 'unpack_read', 'unpack_write', 'final_read'))):
            with self.subTest(options=options):
                report = self.check(row(1, ('test', '', '')), 1, prior_result=True, **options)
                self.assertTrue(report['prior_result_retained'])
                self.assertTrue(report['native_ready_flag'])
                self.assertFalse(report['new_result_published'])

    def test_success_replaces_prior_result(self):
        report = self.check(row(1, ('test', '', '')), 1, prior_result=True)
        self.assertFalse(report['prior_result_retained'])
        self.assertTrue(report['new_result_published'])

    def test_native_request_creator_resets_prior_result(self):
        path = Path(__file__).resolve().parents[1]/'private/demae/v2/main.decompressed.dol'
        if not path.is_file():
            self.skipTest('Private helper executable unavailable')
        for query in (0, 3770813, 9999999):
            report = verify_request_reset(path.read_bytes(), query)
            self.assertTrue(report['prior_result_reset_verified'])
            self.assertFalse(report['real_task_registration_verified'])

    def test_fingerprint_required(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify(b'', bytes(32), bytes(16), bytes(16), 1)
