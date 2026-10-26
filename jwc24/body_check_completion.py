"""Observed HFNJ dataset-read completion and opaque header-pair gate.

These are offline state decisions over explicit synthetic or supplied buffers.
They do not read a profile, perform IO, generate records or authenticate data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import struct
import zlib

from .body_check import DatasetInspection, MAX_DATASET_BYTES, inspect_dataset


class BodyCheckCompletionError(ValueError):
    """Unsupported local state; diagnostics exclude input bytes and values."""


def _signed_word(value):
    if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
        raise BodyCheckCompletionError('Expected an explicit signed native diagnostic word')


@dataclass(frozen=True)
class DatasetReadCompletion:
    buffer: bytes = field(repr=False)
    latched_flag: bool
    diagnostic_code: int = field(repr=False)
    native_return: int
    read_invoked: bool
    header_crc_checked: bool
    header_crc_matches: bool | None
    buffer_cleared: bool
    diagnostic_conversion_requested: bool

    def metadata(self):
        return {'buffer_bytes': len(self.buffer), 'native_return': self.native_return,
                'latched_flag': self.latched_flag, 'read_invoked': self.read_invoked,
                'header_crc_checked': self.header_crc_checked,
                'header_crc_matches': self.header_crc_matches,
                'buffer_cleared': self.buffer_cleared,
                'diagnostic_conversion_requested': self.diagnostic_conversion_requested,
                'filesystem_read_or_crypto_executed': False,
                'dataset_payload_semantics_checked': False,
                'freshness_or_authentication_verified': False,
                'save_or_profile_modified': False, 'native_ui_verified': False}


def evaluate_dataset_read_completion(buffer: bytes, *, read_result: int,
        latched_flag: bool, diagnostic_code: int,
        converted_reader_diagnostic: int | None) -> DatasetReadCompletion:
    """Mirror the complete read-completion consumer's observed branch ordering.

    ``buffer`` is an explicit full 32-KiB memory snapshot *after* the external
    reader boundary, not a file to pad or a dataset to generate. For a prior
    latched flag, no read occurs and the same snapshot is preserved. The reader
    result is opaque unsigned register state; in particular, result 2 returns
    one without checking any header. Neither return bit establishes readiness.

    Result 5 asks an external diagnostic converter for a value. The caller must
    supply that value explicitly; its mapping is not inferred here. Other
    results do not perform that conversion. The diagnostic is retained even
    after a CRC-matching result zero, exactly as in the selected native consumer.
    """
    if type(buffer) is not bytes or len(buffer) != MAX_DATASET_BYTES:
        raise BodyCheckCompletionError('Expected one explicit full native dataset buffer')
    if type(read_result) is not int or not 0 <= read_result <= 0xFFFFFFFF:
        raise BodyCheckCompletionError('Expected an explicit unsigned native reader result')
    if type(latched_flag) is not bool:
        raise BodyCheckCompletionError('Expected an explicit native latched-flag predicate')
    _signed_word(diagnostic_code)
    if converted_reader_diagnostic is not None:
        _signed_word(converted_reader_diagnostic)

    def result(data, flag, diagnostic, returned, invoked, checked=False,
               matches=None, cleared=False, converted=False):
        return DatasetReadCompletion(data, flag, diagnostic, returned, invoked,
                                     checked, matches, cleared, converted)

    if latched_flag:
        return result(buffer, True, diagnostic_code, 0, False)
    if read_result == 2:
        return result(buffer, False, diagnostic_code, 1, True)
    if read_result == 0:
        matches = struct.unpack_from('>I', buffer)[0] == zlib.crc32(buffer[4:16])
        if matches:
            return result(buffer, False, diagnostic_code, 1, True, True, True)
        return result(bytes(MAX_DATASET_BYTES), True, -999, 0, True,
                      True, False, True)
    if read_result == 5:
        if converted_reader_diagnostic is None:
            raise BodyCheckCompletionError('Reader result requires an explicit converted diagnostic')
        return result(bytes(MAX_DATASET_BYTES), True, converted_reader_diagnostic,
                      0, True, cleared=True, converted=True)
    # 0xB006 has its own native branch, with the same observed clear/-5 state
    # as the remaining result values. It is not assigned an invented meaning.
    return result(bytes(MAX_DATASET_BYTES), True, -5, 0, True, cleared=True)


def evaluate_header_pair_gate(first_u16: int, second_u16: int) -> bool:
    """Return the observed predicate over opaque BE16-at-12/14 header words.

    The selected native caller chooses an existing menu transition from this
    bit. The words' complete meaning and that transition's UI remain unverified.
    """
    if any(type(value) is not int or not 0 <= value <= 0xFFFF
           for value in (first_u16, second_u16)):
        raise BodyCheckCompletionError('Expected two explicit unsigned native header words')
    return first_u16 > 1 or (first_u16 == 1 and second_u16 != 0)


@dataclass(frozen=True)
class DatasetHeaderGate:
    inspection: DatasetInspection
    gate_result: bool

    def metadata(self):
        return {**self.inspection.metadata(), 'opaque_header_pair_gate_checked': True,
                'header_pair_gate_result': self.gate_result,
                'native_menu_transition_or_display_verified': False}


def inspect_dataset_header_gate(data: bytes) -> DatasetHeaderGate:
    """Compose the existing safe header inspector and the opaque native gate.

    A CRC match protects only twelve header bytes. Trailing bytes remain opaque,
    with no implied format, health meaning, freshness or cryptographic validity.
    """
    if type(data) is not bytes:
        raise BodyCheckCompletionError('Expected immutable plaintext header bytes')
    inspection = inspect_dataset(data)
    first, second = struct.unpack_from('>HH', data, 12)
    return DatasetHeaderGate(inspection, evaluate_header_pair_gate(first, second))
