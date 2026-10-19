"""Build offline menu-category candidates from validated observed menu facts.

Experimental control fields are not verified service capabilities. Never served
by the fixture server; native model storage/rendering still require tracing.
"""
import hashlib
import xml.etree.ElementTree as ET

from tools.build_demae_area_fixture import native_xml


def build_menu_categories(menu):
    categories = list(dict.fromkeys(item['category'] for item in menu['items']))
    # Conservative inspection bound, not a discovered native capacity.
    if not 1 <= len(categories) <= 32:
        raise ValueError('Expected one to 32 observed menu categories')
    root = ET.Element('response')
    entries = []
    for category in categories:
        category.encode('cp932', errors='strict')
        code = 'M'+hashlib.sha256((menu['source_url']+'\0'+category).encode()).hexdigest()[:12]
        entries.append({'menu_code': code, 'source_category': category,
                        'restaurant_id': menu['restaurant']['restaurant_id']})
        row = ET.SubElement(root, 'row')
        for key, value in {'menuCode': code, 'linkTitle': category, 'enabledLink': '0',
                           'name': category, 'info': menu['source_url'], 'setNum': '0'}.items():
            ET.SubElement(row, key).text = value
        ET.SubElement(row, 'lunchMenuList')
    ET.SubElement(ET.SubElement(root, 'apiStatus'), 'code').text = '0'
    return native_xml(root), entries
