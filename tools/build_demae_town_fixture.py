"""Build a bounded experimental town list, preserving excluded names separately."""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_towns import town_candidates
from jwc24.japan_post import areas
from jwc24.demae_response import inspect_area_response
from tools.build_demae_area_fixture import native_xml
from jwc24.demae_area_registry import AreaRegistry


class NoDisplayableTowns(ValueError):
    """Source municipality has only excluded candidates; no empty success XML."""


def build_towns(database, municipality, *, registry=None):
    if registry is not None and not isinstance(registry, AreaRegistry):
        raise ValueError('Expected a validated area-registry snapshot')
    candidates = town_candidates(database, municipality)
    cities = areas(database, 'JP-' + municipality[:2])
    names = [row['name'] for row in cities if row['id'] == municipality]
    if len(names) != 1:
        raise ValueError('Unknown or ambiguous municipality')
    included = [row for row in candidates if row['label_eligible']]
    excluded = [row for row in candidates if not row['label_eligible']]
    if not included:
        raise NoDisplayableTowns('No displayable town candidates')
    root = ET.Element('response')
    ET.SubElement(ET.SubElement(root, 'apiStatus'), 'code').text = '0'
    ET.SubElement(root, 'areaCount').text = str(len(included))
    container = ET.SubElement(ET.SubElement(root, 'areaList'), 'container0')
    ET.SubElement(container, 'kanji1').text = names[0]
    listing = ET.SubElement(container, 'list')
    for candidate in included:
        row = ET.SubElement(listing, 'row')
        ET.SubElement(row, 'kanji2').text = candidate['name']
        ET.SubElement(row, 'kanji3')
        # Native duplicate-label fallback at0x800F8A54 reads seven postcode
        # bytes. Preserve the source postcode rather than dropping ambiguity.
        ET.SubElement(row, 'zipCode').text = candidate['postal']
        code = (candidate['experimental_code'] if registry is None else
                registry.code_for(municipality, candidate['postal'], candidate['name']))
        ET.SubElement(row, 'areaCode').text = code
        ET.SubElement(row, 'isNextArea').text = '0'
        ET.SubElement(row, 'display').text = '1'
    data = native_xml(root)
    report = inspect_area_response(data, variant='list')
    return data, {**report, 'excluded': excluded, 'decimal_registry_used': registry is not None,
                  'scope': 'offline experimental terminal town rows; native completion unverified'}
