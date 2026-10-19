"""Build an offline 47-prefecture fixture, with explicit synthetic area codes.

Not a production response: wrapper, startup variant and native IDs are unverified.
"""
import json
import re
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_regions import prefectures
from jwc24.demae_response import inspect_area_response
from tools.asset_publication import atomic_write


def native_xml(root):
    """Emit nonempty scalar values as CDATA, as required by HCHJ's lexer."""
    def encode(node):
        if not isinstance(node.tag, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*', node.tag):
            raise ValueError('Invalid native fixture element name')
        if node.attrib or node.tail and node.tail.strip():
            raise ValueError('Unexpected fixture attributes or tail text')
        text = node.text or ''
        if any(ord(char) < 32 and char not in '\t\n\r' for char in text):
            raise ValueError('Invalid XML control character in fixture text')
        try:
            text.encode('cp932', errors='strict')
        except UnicodeEncodeError:
            raise ValueError('Fixture scalar cannot be represented by the CP932 producer policy') from None
        if ']]>' in text:
            raise ValueError('Fixture text contains a CDATA terminator')
        if len(node) and text:
            raise ValueError('Mixed fixture content is unsupported')
        body = ''.join(encode(child) for child in node)
        if text:
            body = '<![CDATA[' + text + ']]>'
        # HCHJ's custom parser only recognizes explicit opening/closing tags.
        # Self-closing empties made sibling rows recurse into one another.
        return f'<{node.tag}>{body}</{node.tag}>'
    return ('<?xml version="1.0" encoding="UTF-8"?>\n' + encode(root)).encode('utf-8')


def build_root_fixture(database=None):
    """State 0x85 reads direct areaList children, not later nested list rows.

    0x800D88F4 finds areaList; 0x800D8A2C reads each child's segment.
    0x800D8AC0 obtains the element name as the selection code.
    """
    root = ET.Element('response')
    area = ET.SubElement(root, 'areaList')
    for region in prefectures():
        row = ET.SubElement(area, 'TEST-' + region['id'])
        ET.SubElement(row, 'segment').text = region['name']
        if database is not None:
            from jwc24.japan_post import areas
            listing = ET.SubElement(row, 'list')
            for city in areas(database, region['id']):
                item = ET.SubElement(listing, 'row')
                ET.SubElement(item, 'areaName').text = city['name']
                ET.SubElement(item, 'areaCode').text = 'M' + city['id']
    status = ET.SubElement(root, 'apiStatus')
    ET.SubElement(status, 'code').text = '0'
    data = native_xml(root)
    inspect_area_response(data, variant='root')
    return data


def build_fixture():
    root = ET.Element('response')
    response = root
    status = ET.SubElement(response, 'apiStatus')
    ET.SubElement(status, 'code').text = '0'
    ET.SubElement(response, 'areaCount').text = '47'
    area = ET.SubElement(response, 'areaList')
    container = ET.SubElement(area, 'container0')
    ET.SubElement(container, 'kanji1').text = '日本'
    listing = ET.SubElement(container, 'list')
    for region in prefectures():
        row = ET.SubElement(listing, 'row')
        ET.SubElement(row, 'kanji2').text = region['name']
        ET.SubElement(row, 'kanji3')
        ET.SubElement(row, 'areaCode').text = 'TEST-' + region['id']
        ET.SubElement(row, 'isNextArea').text = '1'
        ET.SubElement(row, 'display').text = '1'
    return native_xml(root)


def build_postal_fallback_fixture():
    """Exercise the traced no-selectedArea branch, not a successful lookup."""
    root = ET.Element('response')
    response = root
    status = ET.SubElement(response, 'apiStatus')
    ET.SubElement(status, 'code').text = '13'
    data = native_xml(root)
    inspect_area_response(data, variant='postal-fallback')
    return data


def build_auth_fixture():
    root = ET.Element('response')
    response = root
    status = ET.SubElement(response, 'apiStatus')
    ET.SubElement(status, 'code').text = '0'
    ET.SubElement(response, 'authKey').text = 'OFFLINE-TEST-TOKEN'
    data = native_xml(root)
    inspect_area_response(data, variant='auth')
    return data


def build_document_fixture():
    root = ET.Element('response')
    response = root
    status = ET.SubElement(response, 'apiStatus')
    ET.SubElement(status, 'code').text = '0'
    ET.SubElement(response, 'version').text = '1'
    for number in range(3):
        container = ET.SubElement(response, f'container{number}')
        ET.SubElement(container, 'contents').text = 'LOCAL TEST. Orders are not sent.'
    data = native_xml(root)
    inspect_area_response(data, variant='documents')
    return data


def main():
    data = build_fixture()
    report = inspect_area_response(data, variant='list')
    output = Path(__file__).resolve().parents[1] / 'private/demae/fixtures/prefectures.xml'
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(output, data)
    atomic_write(output.with_name('postal-fallback.xml'), build_postal_fallback_fixture())
    atomic_write(output.with_name('auth.xml'), build_auth_fixture())
    atomic_write(output.with_name('documents.xml'), build_document_fixture())
    print(json.dumps({'rows': report['row_count'], 'scope': 'offline synthetic fixture; not served to Dolphin'}))


if __name__ == '__main__':
    main()
