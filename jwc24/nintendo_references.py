"""Offline next-stage list-reference planning from validated HATJ CSData.

No configured service endpoint is inferred, contacted or authorized. The output
is an opaque native-shaped reference, not a downloaded or verified catalog.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import struct

from .nintendo_csdata import decompress_csdata, inspect_csdata

REFERENCE_CAPACITY = 512
LANGUAGES = (b'ja', b'en', b'de', b'fr', b'es', b'it', b'nl')


@dataclass(frozen=True)
class NintendoListReference:
    reference: bytes = field(repr=False)
    identifier_word: int = field(repr=False)
    language_code: int

    def metadata(self):
        return {
            'reference_bytes': len(self.reference),
            'language_code': self.language_code,
            'country_component': 'JP',
            'reference_built': True,
            'endpoint_authorized': False,
            'channel_language_eligibility_checked': False,
            'catalog_downloaded_or_validated': False,
            'record_schema_checked': False,
            'native_browsing_verified': False,
        }


def build_japanese_list_reference(payload: bytes, *, service_prefix: bytes,
                                  language_code: int) -> NintendoListReference:
    """Build the verified Japanese-country reference with explicit configuration.

    The native builder appends bytes without normalization or URL escaping.
    This local helper rejects capacity overflow instead of silently using the
    native helper's truncated reference. Callers must separately authorize the
    resulting endpoint and validate any subsequently downloaded list records.
    BE32-at-0x0C is an observed filename identifier; no date/version semantics
    are assigned to it by this component.
    """
    if (not isinstance(service_prefix, bytes) or not service_prefix
            or len(service_prefix) >= REFERENCE_CAPACITY or b'\0' in service_prefix):
        raise ValueError('Expected a nonempty bounded service-prefix byte string without NULs')
    if type(language_code) is not int or not 0 <= language_code < len(LANGUAGES):
        raise ValueError('Expected a reviewed Nintendo Channel language code')
    inspection = inspect_csdata(payload)
    raw, _compression = decompress_csdata(payload)
    identifier = struct.unpack_from('>I', raw, 0x0C)[0]
    reference = (service_prefix + inspection.reference + b'/list/JP/'
                 + LANGUAGES[language_code] + b'/' + str(identifier).encode('ascii') + b'.LZ')
    if len(reference) >= REFERENCE_CAPACITY:
        raise ValueError('Nintendo Channel list reference exceeds its native buffer capacity')
    return NintendoListReference(reference, identifier, language_code)
