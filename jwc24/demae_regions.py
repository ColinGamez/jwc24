"""Japan catalog coverage, independent of unverified native Demae area codes."""
from jwc24.hbnj_regions import PREFECTURES


def prefectures():
    """Return fresh coverage records; an empty catalog is not delivery support."""
    return [{'id': f'JP-{code:02d}', 'name': name,
             'native_area_code': None, 'catalog_status': 'not_imported',
             'ordering_supported': False} for code, name, _ in PREFECTURES]


def match_provider_areas(areas):
    """Match provider master names, rejecting missing or ambiguous coverage."""
    if not isinstance(areas, list):
        raise ValueError('Provider area master must be a list')
    by_name = {}
    for area in areas:
        if not isinstance(area, dict):
            raise ValueError('Invalid provider area')
        name, code = area.get('name'), area.get('code')
        if not isinstance(name, str) or not isinstance(code, str) or not code:
            raise ValueError('Invalid provider area name or code')
        if name in by_name or code in by_name.values():
            raise ValueError('Duplicate provider area')
        by_name[name] = code
    result = prefectures()
    for row in result:
        name = row['name']
        short = name[:-1] if name[-1] in '都府県' else name
        matches = [by_name[n] for n in {name, short} if n in by_name]
        if len(matches) != 1:
            raise ValueError(f'Missing or ambiguous provider coverage for {row["id"]}')
        row['provider_area_code'] = matches[0]
    return result
