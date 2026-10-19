"""Build offline category framing; not restaurant availability or native proof."""
import re
import xml.etree.ElementTree as ET

from jwc24.demae_response import inspect_area_response
from tools.build_demae_area_fixture import native_xml


def build_categories(codes, *, allow_empty=False):
    codes = list(codes)
    if not (0 if allow_empty else 1) <= len(codes) <= 32:
        raise ValueError('Expected one to 32 distinct experimental category codes')
    if any(not isinstance(code, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,15}', code) for code in codes):
        raise ValueError('Invalid experimental category code')
    if len(set(codes)) != len(codes):
        raise ValueError('Duplicate experimental category code')
    root = ET.Element('response')
    group = ET.SubElement(root, 'container0')
    ET.SubElement(group, 'LargeCategoryName').text = '食事'
    listing = ET.SubElement(group, 'CategoryList')
    for code in codes:
        ET.SubElement(ET.SubElement(listing, 'row'), 'CategoryCode').text = code
    # Placing status first would make native child-count-minus-one iteration
    # process it as a group and omit the final real category group.
    ET.SubElement(ET.SubElement(root, 'apiStatus'), 'code').text = '0'
    data = native_xml(root)
    inspect_area_response(data, variant='categories')
    return data
