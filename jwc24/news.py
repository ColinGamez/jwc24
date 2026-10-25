"""Bounded, offline News Channel structural inspection.

Japanese HAGJ v7 native validation establishes the header/table/record anchors.
Headline table and semantic field-name leads are separately attributed to the
public WiiLink generator. This module neither fetches news nor serves success.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import struct
import zlib

from .forecast import decode_lz10

HEADER_SIZE = 104
ENVELOPE_SIZE = 320
MAX_RAW_BYTES = 4 * 1024 * 1024
MAX_ENVELOPE_BYTES = 5 * 1024 * 1024
MAX_RECORDS = 4096
MAX_TOPIC_REFERENCES = 65536
MAX_DECODED_TEXT_BYTES = 8 * 1024 * 1024
NONE_INDEX = 0xFFFFFFFF
TOPIC = struct.Struct('>3I')
ARTICLE = struct.Struct('>11I')
SOURCE = struct.Struct('>BBH6I')
LOCATION = struct.Struct('>IhhBBHB3x')
IMAGE = struct.Struct('>6I')
HEADLINE = struct.Struct('>2I')


class NewsFormatError(ValueError):
    """Input violates the reviewed structural subset or local safety policy."""


@dataclass(frozen=True)
class ArticleRecord:
    identifier: int = field(repr=False)
    source_index: int
    location_index: int
    picture_timestamp: int
    picture_index: int
    published_timestamp: int
    updated_timestamp: int
    headline: str = field(repr=False)
    text: str = field(repr=False)


@dataclass(frozen=True)
class NewsInspection:
    byte_length: int
    version: int
    updated_timestamp: int
    close_timestamp: int
    secondary_timestamp: int
    country_code: int
    language_code: int
    supported_languages: tuple[int, ...]
    server_message_present: bool
    topics: int
    articles: tuple[ArticleRecord, ...] = field(repr=False)
    sources: int
    locations: int
    images: int
    headlines: int
    topic_references: int
    external_topic_references: int
    external_image_references: int
    topic_links: tuple[tuple[int, int], ...] = field(repr=False)
    buffer_sha256: str = field(repr=False)

    def metadata(self):
        """Exclude article/source/location text, identifiers and binary media."""
        return {
            'byte_length': self.byte_length, 'version': self.version,
            'country_code': self.country_code, 'language_code': self.language_code,
            'server_message_present': self.server_message_present,
            'topics': self.topics, 'articles': len(self.articles),
            'sources': self.sources, 'locations': self.locations,
            'images': self.images, 'headlines': self.headlines,
            'topic_references': self.topic_references,
            'external_topic_references': self.external_topic_references,
            'external_image_references': self.external_image_references,
            'crc32_checked': True, 'cross_buffer_references_checked': False,
            'signatures_checked': False, 'current_validity_checked': False,
            'native_delivery_or_rendering_checked': False,
            'scope': 'bounded single-buffer structural inspection; local safety restrictions apply',
        }


def inspect_news(raw: bytes) -> NewsInspection:
    """Inspect one decompressed buffer, retaining explicit cross-hour gaps.

    Native timestamps are minutes since 2000-01-01. This function reports no
    current/fresh-content result. It rejects unsafe wraparound/overlapping table
    ranges, malformed UTF-16, incomplete terminators and body sizes that the
    native latest-topic pass would prune; these are deliberate local policies.
    """
    if not isinstance(raw, bytes) or not HEADER_SIZE <= len(raw) <= MAX_RAW_BYTES:
        raise NewsFormatError('News input is outside the local byte bounds')

    def word(offset):
        return struct.unpack_from('>I', raw, offset)[0]

    version, size, checksum = struct.unpack_from('>3I', raw)
    if version >> 16:
        raise NewsFormatError('Unsupported News version high word')
    if size != len(raw):
        raise NewsFormatError('News declared and actual sizes differ')
    if zlib.crc32(raw[12:]) & 0xFFFFFFFF != checksum:
        raise NewsFormatError('News CRC32 mismatch')
    supported = raw[28:44]
    try:
        terminator = supported.index(0xFF)
    except ValueError:
        raise NewsFormatError('News supported-language list lacks its terminator') from None
    languages = tuple(supported[:terminator])
    if any(value >= 7 for value in languages):
        raise NewsFormatError('News supported-language code is outside the reviewed range')
    if raw[45] >= 2 or raw[46] >= 2:
        raise NewsFormatError('News header flag is outside its reviewed range')

    table_info = (('topic', 52, TOPIC), ('article', 60, ARTICLE),
                  ('source', 68, SOURCE), ('location', 76, LOCATION),
                  ('image', 84, IMAGE), ('headline', 96, HEADLINE))
    tables, table_ranges = {}, []
    for label, position, layout in table_info:
        count, offset = struct.unpack_from('>2I', raw, position)
        if count > MAX_RECORDS or offset & 3 or offset > len(raw):
            raise NewsFormatError('News table count, alignment or offset is invalid')
        end = offset + count * layout.size
        if end > len(raw) or (count and offset < HEADER_SIZE):
            raise NewsFormatError('News table exceeds its bounded data region')
        if count:
            if any(offset < other_end and end > other_start for other_start, other_end in table_ranges):
                raise NewsFormatError('News tables overlap')
            table_ranges.append((offset, end))
        tables[label] = tuple(layout.unpack_from(raw, offset + index * layout.size)
                              for index in range(count))

    decoded_bytes, text_cache = 0, {}

    def decoded_text(offset, end):
        nonlocal decoded_bytes
        key = offset, end
        if key in text_cache:
            return text_cache[key]
        if end - offset > MAX_DECODED_TEXT_BYTES - decoded_bytes:
            raise NewsFormatError('News decoded text exceeds local aggregate byte limit')
        try:
            value = raw[offset:end].decode('utf-16-be')
        except UnicodeDecodeError:
            raise NewsFormatError('News text contains malformed UTF-16BE') from None
        decoded_bytes += end - offset
        text_cache[key] = value
        return value

    def data_range(offset, length, *, alignment=1):
        if (offset < HEADER_SIZE or offset % alignment or length < 0
                or offset + length > len(raw)
                or any(offset < hi and offset + length > lo for lo, hi in table_ranges)):
            raise NewsFormatError('News data reference exceeds or overlaps its bounded region')

    def terminated(offset, *, limit=4096):
        data_range(offset, 2, alignment=2)
        end = offset
        while end + 2 <= len(raw) and end - offset <= limit:
            if raw[end:end + 2] == b'\0\0':
                data_range(offset, end - offset + 2, alignment=2)
                return decoded_text(offset, end)
            end += 2
        raise NewsFormatError('News text terminator exceeds its bounded region')

    def sized_text(length, offset, *, body=False):
        if length == 0:
            if offset:
                raise NewsFormatError('News empty text has a nonzero offset')
            return ''
        if length & 1 or (body and length >= 20000):
            raise NewsFormatError('News text length violates local UTF-16/body policy')
        data_range(offset, length + 2, alignment=2)
        if raw[offset + length:offset + length + 2] != b'\0\0':
            raise NewsFormatError('News sized text lacks a following terminator')
        return decoded_text(offset, offset + length)

    message = word(48)
    if message >= len(raw) or message & 1:
        raise NewsFormatError('News message offset is invalid')
    if message:
        terminated(message, limit=1022)
    for logo, position, _reserved, picture_size, picture_offset, name_size, name_offset, copyright_size, copyright_offset in tables['source']:
        if logo >= 7 or not 1 <= position < 7:
            raise NewsFormatError('News source flags are invalid')
        if (logo == 0) != bool(picture_size) or (logo == 0) != bool(picture_offset):
            raise NewsFormatError('News source picture fields conflict with its logo flag')
        if picture_size:
            data_range(picture_offset, picture_size)
        sized_text(name_size, name_offset)
        sized_text(copyright_size, copyright_offset)
    for name_offset, _lat, _lon, _country, _region, _location, _zoom in tables['location']:
        terminated(name_offset)
    for credit_size, credit_offset, caption_size, caption_offset, picture_size, picture_offset in tables['image']:
        sized_text(credit_size, credit_offset)
        sized_text(caption_size, caption_offset)
        if not picture_size or not picture_offset:
            raise NewsFormatError('News image has no bounded picture data')
        data_range(picture_offset, picture_size)
    for length, offset in tables['headline']:
        sized_text(length, offset)

    articles, identifiers, external_images = [], set(), 0
    updated = word(12)
    for values in tables['article']:
        identifier, source, location, picture_time, picture, published, changed, title_size, title_offset, body_size, body_offset = values
        if identifier in identifiers:
            raise NewsFormatError('News article identifiers repeat within a buffer')
        identifiers.add(identifier)
        if source != NONE_INDEX and source >= len(tables['source']):
            raise NewsFormatError('News article references a missing local source')
        if location != NONE_INDEX and location >= len(tables['location']):
            raise NewsFormatError('News article references a missing local location')
        if picture_time:
            if picture_time == updated:
                if picture != NONE_INDEX and picture >= len(tables['image']):
                    raise NewsFormatError('News article references a missing local image')
            else:
                external_images += 1
        articles.append(ArticleRecord(identifier, source, location, picture_time, picture,
                                     published, changed, sized_text(title_size, title_offset),
                                     sized_text(body_size, body_offset, body=True)))
    references = external_references = 0
    topic_links = []
    for index, (name_offset, count, offset) in enumerate(tables['topic']):
        if name_offset:
            terminated(name_offset)
        elif index:
            raise NewsFormatError('News topic outside slot zero has no name')
        if count > MAX_TOPIC_REFERENCES - references:
            raise NewsFormatError('News topic reference count exceeds local limit')
        references += count
        if count:
            data_range(offset, count * 8, alignment=4)
        elif offset and (offset & 3 or offset > len(raw)):
            raise NewsFormatError('News empty timestamp table offset is invalid')
        for position in range(count):
            timestamp, identifier = struct.unpack_from('>2I', raw, offset + position * 8)
            topic_links.append((timestamp, identifier))
            if timestamp == updated:
                if identifier not in identifiers:
                    raise NewsFormatError('News topic references a missing local article')
            else:
                external_references += 1
    return NewsInspection(len(raw), version, updated, word(16), word(24), raw[20], raw[44],
                          languages, bool(message), len(tables['topic']), tuple(articles), len(tables['source']),
                          len(tables['location']), len(tables['image']), len(tables['headline']),
                          references, external_references, external_images,
                          tuple(topic_links), hashlib.sha256(raw).hexdigest())


def inspect_news_envelope(payload: bytes) -> NewsInspection:
    """Decode the existing 320-byte-envelope/LZ10 shape without checking trust.

    The envelope shape is corroborated by public restoration implementations;
    this function does not execute the native signature/download path.
    """
    if (not isinstance(payload, bytes)
            or not ENVELOPE_SIZE + 4 <= len(payload) <= MAX_ENVELOPE_BYTES):
        raise NewsFormatError('News envelope is outside local byte bounds')
    compressed = payload[ENVELOPE_SIZE:]
    if compressed[0] != 0x10:
        raise NewsFormatError('News envelope does not contain the reviewed LZ10 shape')
    expected = int.from_bytes(compressed[1:4], 'little')
    if not HEADER_SIZE <= expected <= MAX_RAW_BYTES:
        raise NewsFormatError('News decompressed length is outside local byte bounds')
    try:
        raw = decode_lz10(compressed)
    except ValueError:
        raise NewsFormatError('News LZ10 stream is malformed or truncated') from None
    return inspect_news(raw)
