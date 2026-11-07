"""Standard vectors and original CMOC hash/string-check execution."""
from pathlib import Path
import hmac
import unittest

from jwc24.cmoc_hash import hmac_sha1_digest, inspect_application_hash


def rfc2202_vectors():
    # RFC Editor, RFC 2202 section 3; public synthetic interoperability vectors.
    return (
        (b'\x0b' * 20, b'Hi There', 'b617318655057264e28bc0b6fb378c8ef146be00'),
        (b'Jefe', b'what do ya want for nothing?', 'effcdf6ae5eb2fa2d27416d5f184df9c259a7c79'),
        (b'\xaa' * 20, b'\xdd' * 50, '125d7342b9ac11cd91a39af48aa17b4f63f175d3'),
        (bytes(range(1, 26)), b'\xcd' * 50, '4c9007f4026250c6bc8414f9bf50c86c2d7235da'),
        (b'\x0c' * 20, b'Test With Truncation', '4c1a03424b55e07fe7f27be1d58bb9324a9a5a04'),
        (b'\xaa' * 80, b'Test Using Larger Than Block-Size Key - Hash Key First',
         'aa4ae5e15272d00e95705637ce8a3b55ed402112'),
        (b'\xaa' * 80, b'Test Using Larger Than Block-Size Key and Larger Than One Block-Size Data',
         'e8e99d0f45237d786d6bbaa7965c7808bbff1a91'),
    )


def splits(message):
    return ((message,), (b'', message[:1], b'', message[1:], b''),
            tuple(message[i:i + 13] for i in range(0, len(message), 13)))


def nul_fixture(position):
    key = b'S' * 20
    for i in range(10000):
        message = b'cmoc synthetic zero ' + str(i).encode('ascii')
        digest = hmac.digest(key, message, 'sha1')
        if digest.find(b'\0') == position:
            return key, (message,), digest
    raise AssertionError('Deterministic synthetic zero-byte fixture unavailable')


def sdk_cases():
    result = []
    for key, message, _ in rfc2202_vectors():
        result.extend((key, chunks) for chunks in splits(message))
    for key_length in (0, 1, 20, 64, 65, 80, 128):
        key = bytes(i % 256 for i in range(key_length))
        for length in (0, 1, 55, 56, 63, 64, 65, 127, 128, 129, 1024):
            message = bytes(i % 256 for i in range(length))
            result.append((key, (message[:55], b'', message[55:64], message[64:])))
    return result


def application_cases():
    result = []
    for size in range(1, 21):
        key = bytes(range(1, size + 1))
        chunks = (b'part-one\0', b'', b'part-two')
        digest = hmac_sha1_digest(key, chunks)
        result.append(dict(key=key, key_size=size, chunks=chunks, expected=digest[:size]))
        for position in sorted({0, size // 2, size - 1}):
            bad = bytearray(digest[:size])
            bad[position] ^= 0xFF
            result.append(dict(key=key, key_size=size, chunks=chunks, expected=bytes(bad)))
    for key, size in ((None, 0), (b'\0', 0), (b'\0ignored', 0), (b'A\0B', 0),
                      (b'A\0B', 3), (b'Jefe\0ignored', 0), (b'Jefe ignored', 4)):
        chunks = (b'', b'binary\0message', b'')
        selected = b'' if key is None else key[:size] if size else key.split(b'\0', 1)[0]
        expected = b'' if key is None else hmac_sha1_digest(selected, chunks)[:len(selected)]
        result.append(dict(key=key, key_size=size, chunks=chunks, expected=expected))
    for position in (0, 8, 19):
        key, chunks, digest = nul_fixture(position)
        result.append(dict(key=key, key_size=20, chunks=chunks, expected=digest))
        bad = bytearray(digest)
        bad[position + 1 if position < 19 else position - 1] ^= 0xFF
        result.append(dict(key=key, key_size=20, chunks=chunks, expected=bytes(bad)))
    return result


class HashTests(unittest.TestCase):
    def test_all_seven_rfc2202_sha1_vectors_and_chunking(self):
        for key, message, expected in rfc2202_vectors():
            for chunks in splits(message):
                self.assertEqual(hmac_sha1_digest(key, chunks).hex(), expected)

    def test_native_key_size_is_independent_of_algorithm_output_size(self):
        for size in range(1, 21):
            key = b'K' * size
            chunks = (b'message',)
            digest = hmac_sha1_digest(key, chunks)
            result = inspect_application_hash(key=key, key_size=size, chunks=chunks, expected=digest[:size])
            self.assertEqual(result.resolved_key_size, size)
            self.assertEqual(len(result.digest), 20)
            self.assertTrue(result.native_match)
            self.assertTrue(result.full_span_binary_match)
            self.assertFalse(result.metadata()['native_check_establishes_authentication'])

    def test_null_key_disables_but_present_empty_key_accepts_zero_comparison(self):
        disabled = inspect_application_hash(key=None, key_size=0, chunks=(b'message',), expected=b'')
        empty = inspect_application_hash(key=b'\0', key_size=0, chunks=(b'message',), expected=b'')
        self.assertFalse(disabled.enabled)
        self.assertEqual(disabled.update_returns, (0,))
        self.assertFalse(disabled.native_match)
        self.assertTrue(empty.enabled)
        self.assertEqual(empty.update_returns, (7,))
        self.assertTrue(empty.native_match)
        self.assertEqual(empty.native_compared_bytes, 0)

    def test_zero_size_uses_c_string_but_nonzero_size_preserves_binary_key(self):
        chunks = (b'message',)
        for size, selected in ((0, b'A'), (3, b'A\0B')):
            result = inspect_application_hash(key=b'A\0B', key_size=size, chunks=chunks,
                                              expected=hmac_sha1_digest(selected, chunks)[:len(selected)])
            self.assertEqual(result.resolved_key_size, len(selected))
            self.assertEqual(result.digest, hmac_sha1_digest(selected, chunks))

    def test_equal_nul_stops_native_check_and_can_hide_later_mismatch(self):
        for position in (0, 8, 19):
            key, chunks, digest = nul_fixture(position)
            bad = bytearray(digest)
            bad[position + 1 if position < 19 else position - 1] ^= 0xFF
            result = inspect_application_hash(key=key, key_size=20, chunks=chunks, expected=bytes(bad))
            self.assertEqual(result.native_match, position < 19)
            self.assertFalse(result.full_span_binary_match)
            if position < 19:
                self.assertTrue(result.stopped_on_equal_nul)
                self.assertEqual(result.native_compared_bytes, position + 1)

    def test_boundaries_privacy_and_overlong_application_comparison(self):
        for changes in (dict(key=b'K' * 21, key_size=21, expected=bytes(21)),
                        dict(key=b'A', key_size=2), dict(key_size=True),
                        dict(expected=b''), dict(chunks=[b'private-marker']),
                        dict(key='private-marker'), dict(chunks=(bytes(1024 * 1024 + 1),))):
            values = dict(key=b'K', key_size=1, chunks=(b'message',), expected=b'x')
            values.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError) as caught:
                inspect_application_hash(**values)
            self.assertNotIn('private-marker', str(caught.exception))
        for key in (b'', b'private-marker'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                inspect_application_hash(key=key, key_size=0, chunks=(), expected=b'')
        result = inspect_application_hash(key=b'private-marker', key_size=14,
                                          chunks=(b'private-marker',), expected=b'private-marker')
        self.assertNotIn('private-marker', repr(result))
        self.assertNotIn('private-marker', str(result.metadata()))


class HashNativeTests(unittest.TestCase):
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

    def test_original_sdk_standard_vectors_binary_keys_chunk_and_block_boundaries(self):
        from tools.verify_cmoc_hash import verify_hmac_sha1
        for index, (key, chunks) in enumerate(sdk_cases()):
            with self.subTest(case=index):
                result = verify_hmac_sha1(self.source, key=key, chunks=chunks)
                self.assertTrue(result['full_twenty_byte_digest_matches'])
                self.assertTrue(result['input_and_stack_guards_verified'])
                self.assertFalse(result['stubs_used'])

    def test_original_application_size_string_comparison_and_failure_semantics(self):
        from tools.verify_cmoc_hash import verify_application_hash
        for index, case in enumerate(application_cases()):
            with self.subTest(case=index):
                result = verify_application_hash(self.source, **case)
                self.assertTrue(result['original_sha1_hmac_string_comparison_executed'])
                self.assertTrue(result['input_and_stack_guards_verified'])
                self.assertFalse(result['stubs_used'])

    def test_overlong_comparison_reaches_actual_digest_boundary_without_reading_stack_tail(self):
        from tools.verify_cmoc_hash import probe_overlong_comparison
        for size in (21, 25, 64):
            key = b'K' * size
            chunks = (b'Hi There',)
            while b'\0' in hmac_sha1_digest(key, chunks):
                chunks = (chunks[0] + b'!',)
            result = probe_overlong_comparison(self.source, key=key, chunks=chunks)
            self.assertTrue(result['digest_overread_trapped'])
            self.assertTrue(result['unrelated_stack_byte_not_read'])
            self.assertEqual(result['comparison_size'], size)


if __name__ == '__main__':
    unittest.main()
