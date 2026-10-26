"""Encode explicitly supplied News records into the recovered native tables.

No articles, categories, dates, positions, source credits or artwork are
inferred. Opaque header/record fields must also be supplied deliberately.
This component does not acquire content, verify its rights, sign or publish it.
"""
from __future__ import annotations

import base64
import binascii
import re
import struct
import zlib

from .news import (ARTICLE, HEADLINE, HEADER_SIZE, IMAGE, MAX_RAW_BYTES,
                   MAX_RECORDS, MAX_TOPIC_REFERENCES, NONE_INDEX, SOURCE,
                   TOPIC, NewsFormatError, inspect_news)

MAX_SPEC_BYTES = 16 * 1024 * 1024
LOCATION_WITH_PADDING = struct.Struct('>IhhBBHB3s')


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise NewsFormatError('News record object has missing or unsupported fields')
    return dict(value)


def _sequence(value, maximum=MAX_RECORDS):
    if type(value) not in (list, tuple) or len(value) > maximum:
        raise NewsFormatError('News record sequence exceeds its explicit local bounds')
    return tuple(value)


def _integer(value, minimum=0, maximum=0xFFFFFFFF):
    if type(value) is not int or not minimum <= value <= maximum:
        raise NewsFormatError('News numeric field exceeds its explicit wire range')
    return value


def _index(value):
    return NONE_INDEX if value is None else _integer(value, maximum=MAX_RECORDS - 1)


def _reference(value):
    if (type(value) is not str or not value.strip() or len(value) > 2048
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise NewsFormatError('News build requires bounded explicit evidence and rights references')
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise NewsFormatError('News evidence reference is not valid text') from None


def _opaque(value, size):
    if type(value) is not str or re.fullmatch('[0-9a-fA-F]{' + str(size * 2) + '}', value) is None:
        raise NewsFormatError('News opaque field requires its exact explicit hexadecimal bytes')
    return bytes.fromhex(value)


def _picture(value):
    value = _fields(value, ('encoding', 'data_base64'))
    text = value['data_base64']
    if (value['encoding'] != 'native-image-bytes' or type(text) is not str
            or not text or len(text) > 4 * ((MAX_RAW_BYTES + 2) // 3)):
        raise NewsFormatError('News image requires bounded explicit native image bytes')
    try:
        data = base64.b64decode(text, validate=True)
    except (ValueError, binascii.Error):
        raise NewsFormatError('News image base64 is malformed') from None
    if not data or len(data) > MAX_RAW_BYTES:
        raise NewsFormatError('News image exceeds local binary bounds')
    return data


def encode_news_records(document: dict) -> bytes:
    """Build one native raw snapshot without filling missing editorial facts.

    Exact schema/field names are documented in channels/news/record_builder.md.
    Derived sizes, aligned offsets, string terminators and CRC are transport
    bookkeeping. Supplied text/dates/flags/opaque bytes remain unchanged.
    The independent inspector validates the completed buffer before return;
    cross-snapshot references still need the separate 24-buffer graph check.
    """
    document = _fields(document, ('schema_version', 'evidence_ref', 'rights_ref',
                                 'header', 'topics', 'articles', 'sources',
                                 'locations', 'images', 'headlines'))
    if type(document['schema_version']) is not int or document['schema_version'] != 1:
        raise NewsFormatError('Unsupported News record specification version')
    _reference(document['evidence_ref'])
    _reference(document['rights_ref'])
    header = _fields(document['header'], (
        'version', 'updated_timestamp', 'close_timestamp', 'secondary_timestamp',
        'country_code', 'language_code', 'supported_languages', 'flags_45_46',
        'byte_47', 'opaque_21_23', 'opaque_92_95', 'server_message'))
    version = _integer(header['version'], maximum=0xFFFF)
    updated = _integer(header['updated_timestamp'])
    closed = _integer(header['close_timestamp'])
    secondary = _integer(header['secondary_timestamp'])
    country = _integer(header['country_code'], maximum=255)
    language = _integer(header['language_code'], maximum=6)
    languages = _sequence(header['supported_languages'], 15)
    languages = bytes(_integer(value, maximum=6) for value in languages)
    flags = _sequence(header['flags_45_46'], 2)
    if len(flags) != 2:
        raise NewsFormatError('News header needs both explicit flag bytes')
    flags = bytes(_integer(value, maximum=1) for value in flags)
    byte_47 = _integer(header['byte_47'], maximum=255)
    opaque_21_23 = _opaque(header['opaque_21_23'], 3)
    opaque_92_95 = _opaque(header['opaque_92_95'], 4)
    rows = {name: _sequence(document[name]) for name in
            ('topics', 'articles', 'sources', 'locations', 'images', 'headlines')}
    # The original latest-topic traversal uses table entry zero. Its safe
    # producer subset must supply that entry instead of manufacturing one.
    if not rows['topics']:
        raise NewsFormatError('News records need an explicit latest-topic entry')
    layouts = (('topics', 52, TOPIC), ('articles', 60, ARTICLE),
               ('sources', 68, SOURCE), ('locations', 76, LOCATION_WITH_PADDING),
               ('images', 84, IMAGE), ('headlines', 96, HEADLINE))
    data = bytearray(HEADER_SIZE)
    tables = {}
    for name, position, layout in layouts:
        tables[name] = len(data)
        struct.pack_into('>II', data, position, len(rows[name]), len(data))
        data.extend(bytes(len(rows[name]) * layout.size))

    def append(value):
        offset = len(data)
        padded_length = (len(value) + 3) & ~3
        if padded_length > MAX_RAW_BYTES - offset:
            raise NewsFormatError('Encoded News records exceed the local raw byte bound')
        data.extend(value)
        data.extend(bytes(padded_length - len(value)))
        return offset

    def text(value, *, required=False, terminated_limit=None, body=False):
        if type(value) is not str or '\0' in value or (required and not value.strip()):
            raise NewsFormatError('News text must be explicit valid text without embedded NUL')
        if len(value) > MAX_RAW_BYTES:
            raise NewsFormatError('News text exceeds the local byte bound')
        try:
            encoded = value.encode('utf-16-be')
        except UnicodeError:
            raise NewsFormatError('News text contains malformed UTF-16') from None
        if (len(encoded) > MAX_RAW_BYTES or (body and len(encoded) >= 20000)
                or (terminated_limit is not None and len(encoded) > terminated_limit)):
            raise NewsFormatError('News text exceeds its reviewed field bound')
        if not encoded:
            return 0, 0
        return len(encoded), append(encoded + bytes(2))

    def picture(value):
        encoded = _picture(value)
        return len(encoded), append(encoded)

    struct.pack_into('>5I', data, 0, version, 0, 0, updated, closed)
    data[20] = country
    data[21:24] = opaque_21_23
    struct.pack_into('>I', data, 24, secondary)
    data[28:44] = languages + bytes([255]) * (16 - len(languages))
    data[44:48] = bytes([language]) + flags + bytes([byte_47])
    data[92:96] = opaque_92_95
    message = header['server_message']
    message_offset = 0 if message is None else text(message, required=True, terminated_limit=1022)[1]
    struct.pack_into('>I', data, 48, message_offset)

    for index, row in enumerate(rows['sources']):
        row = _fields(row, ('logo_flag', 'position', 'reserved_u16', 'picture',
                            'name', 'copyright'))
        logo = _integer(row['logo_flag'], maximum=6)
        position = _integer(row['position'], 1, 6)
        reserved = _integer(row['reserved_u16'], maximum=0xFFFF)
        if logo == 0:
            picture_size, picture_offset = picture(row['picture'])
        elif row['picture'] is None:
            picture_size, picture_offset = 0, 0
        else:
            raise NewsFormatError('News source picture conflicts with its supplied logo flag')
        name_size, name_offset = text(row['name'], required=True)
        copyright_size, copyright_offset = text(row['copyright'])
        SOURCE.pack_into(data, tables['sources'] + index * SOURCE.size,
                         logo, position, reserved, picture_size, picture_offset,
                         name_size, name_offset, copyright_size, copyright_offset)

    for index, row in enumerate(rows['locations']):
        row = _fields(row, ('name', 'latitude_word', 'longitude_word', 'country_code',
                            'region_code', 'location_code', 'zoom_byte', 'opaque_padding'))
        _, name = text(row['name'], required=True, terminated_limit=4096)
        LOCATION_WITH_PADDING.pack_into(
            data, tables['locations'] + index * LOCATION_WITH_PADDING.size, name,
            _integer(row['latitude_word'], -32768, 32767),
            _integer(row['longitude_word'], -32768, 32767),
            _integer(row['country_code'], maximum=255),
            _integer(row['region_code'], maximum=255),
            _integer(row['location_code'], maximum=0xFFFF),
            _integer(row['zoom_byte'], maximum=255), _opaque(row['opaque_padding'], 3))

    for index, row in enumerate(rows['images']):
        row = _fields(row, ('credit', 'caption', 'picture'))
        credit_size, credit = text(row['credit'])
        caption_size, caption = text(row['caption'])
        picture_size, picture_offset = picture(row['picture'])
        IMAGE.pack_into(data, tables['images'] + index * IMAGE.size,
                        credit_size, credit, caption_size, caption, picture_size, picture_offset)

    for index, row in enumerate(rows['articles']):
        row = _fields(row, ('identifier', 'source_index', 'location_index', 'picture_timestamp',
                            'picture_index', 'published_timestamp', 'updated_timestamp',
                            'title', 'body'))
        identifier = _integer(row['identifier'])
        source = _index(row['source_index'])
        location = _index(row['location_index'])
        image_time = _integer(row['picture_timestamp'])
        image_index = _index(row['picture_index'])
        if not image_time and image_index != NONE_INDEX:
            raise NewsFormatError('News image index has no explicit snapshot timestamp')
        published = _integer(row['published_timestamp'])
        changed = _integer(row['updated_timestamp'])
        title_size, title = text(row['title'], required=True)
        body_size, body_offset = text(row['body'], required=True, body=True)
        ARTICLE.pack_into(data, tables['articles'] + index * ARTICLE.size,
                          identifier, source, location, image_time, image_index,
                          published, changed, title_size, title, body_size, body_offset)

    references = 0
    for index, row in enumerate(rows['topics']):
        row = _fields(row, ('name', 'article_links'))
        if row['name'] is None and index == 0:
            name = 0
        else:
            _, name = text(row['name'], required=True, terminated_limit=4096)
        links = _sequence(row['article_links'], MAX_TOPIC_REFERENCES - references)
        references += len(links)
        pairs = bytearray()
        for link in links:
            link = _sequence(link, 2)
            if len(link) != 2:
                raise NewsFormatError('News topic link needs an explicit timestamp and identifier')
            pairs.extend(struct.pack('>II', _integer(link[0]), _integer(link[1])))
        links_offset = append(pairs) if pairs else 0
        TOPIC.pack_into(data, tables['topics'] + index * TOPIC.size, name, len(links), links_offset)

    for index, value in enumerate(rows['headlines']):
        length, offset = text(value, required=True)
        HEADLINE.pack_into(data, tables['headlines'] + index * HEADLINE.size, length, offset)
    struct.pack_into('>I', data, 4, len(data))
    struct.pack_into('>I', data, 8, zlib.crc32(data[12:]) & 0xFFFFFFFF)
    result = bytes(data)
    inspect_news(result)
    return result
