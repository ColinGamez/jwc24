"""Build inspected municipality XML for all prefectures, without altering Wii saves.

Synthetic JIS-derived codes are for offline protocol experiments only.
"""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.japan_post import areas
from jwc24.demae_response import inspect_area_response
from tools.build_demae_area_fixture import native_xml
from tools.asset_publication import atomic_write


def build_municipalities(database, prefecture):
    regions = {row['id']: row['name'] for row in areas(database)}
    if prefecture not in regions:
        raise ValueError('Unknown prefecture')
    cities = areas(database, prefecture)
    if not cities or len(cities) > 2000:
        raise ValueError('Invalid municipality coverage')
    root = ET.Element('response')
    ET.SubElement(ET.SubElement(root, 'apiStatus'), 'code').text = '0'
    ET.SubElement(root, 'areaCount').text = str(len(cities))
    container = ET.SubElement(ET.SubElement(root, 'areaList'), 'container0')
    ET.SubElement(container, 'kanji1').text = regions[prefecture]
    listing = ET.SubElement(container, 'list')
    for city in cities:
        row = ET.SubElement(listing, 'row')
        ET.SubElement(row, 'kanji2').text = city['name']
        ET.SubElement(row, 'kanji3')
        ET.SubElement(row, 'areaCode').text = 'M' + city['id']
        ET.SubElement(row, 'isNextArea').text = '1'
        ET.SubElement(row, 'display').text = '1'
    data = native_xml(root)
    report = inspect_area_response(data, variant='list')
    if report['area_codes_over_15_utf8_bytes']:
        raise ValueError('Municipality identifier exceeds native capacity')
    return data, report


def main():
    base = Path(__file__).resolve().parents[1] / 'private/demae'
    database = base / 'postal/postal.sqlite'
    output = base / 'fixtures/municipalities'
    # Validate the entire set before publishing any fixture.
    fixtures = [(region['id'], *build_municipalities(database, region['id']))
                for region in areas(database)]
    if len(fixtures) != 47:
        raise ValueError('All 47 prefectures are required')
    output.mkdir(parents=True, exist_ok=True)
    for identity, data, report in fixtures:
        atomic_write(output / (identity + '.xml'), data)
    summary = {'prefectures': len(fixtures),
               'municipality_rows': sum(report['row_count'] for _, _, report in fixtures),
               'native_area_codes_verified': False,
               'scope': 'offline municipality fixtures; not connected to native channel'}
    atomic_write(output / 'summary.json', (json.dumps(summary, indent=2) + '\n').encode())
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
