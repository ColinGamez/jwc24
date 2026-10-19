"""Read-only restaurant discovery; directory entries are not delivery offers."""
import math


def parse_osm_restaurants(document: dict) -> list[dict]:
    if not isinstance(document, dict) or document.get('remark'):
        raise ValueError('Overpass returned an incomplete or invalid result')
    elements = document.get('elements')
    if not isinstance(elements, list):
        raise ValueError('Overpass result has no elements list')
    result, seen = [], set()
    for item in elements:
        if not isinstance(item, dict):
            continue
        tags = item.get('tags', {})
        if not isinstance(tags, dict) or tags.get('amenity') not in ('restaurant', 'fast_food', 'cafe'):
            continue
        kind, identity = item.get('type'), item.get('id')
        name = tags.get('name:ja') or tags.get('name')
        if kind not in ('node', 'way', 'relation') or type(identity) is not int or identity <= 0 or not isinstance(name, str) or not name.strip():
            continue
        key = f'osm:{kind}:{identity}'
        if key in seen:
            continue
        center = item if kind == 'node' else item.get('center', {})
        if not isinstance(center, dict):
            continue
        lat, lon = center.get('lat'), center.get('lon')
        if any(type(v) not in (float, int) or not math.isfinite(v) for v in (lat, lon)) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            continue
        seen.add(key)
        def text(field):
            value = tags.get(field)
            return value.strip() if isinstance(value, str) and value.strip() else None
        result.append({'id': key, 'name': name.strip(), 'latitude': lat, 'longitude': lon,
                       'brand': text('brand'), 'cuisine': text('cuisine'),
                       'opening_hours_text': text('opening_hours'), 'website': text('website'),
                       'source_url': f'https://www.openstreetmap.org/{kind}/{identity}',
                       'delivery_tag': text('delivery'), 'delivery_available': None,
                       'menu_items': None, 'minimum_order_yen': None, 'ordering_supported': False})
    return sorted(result, key=lambda r: r['id'])
