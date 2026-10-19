"""Read-only Hot Pepper category snapshots for known replacement-service areas."""
import re
import unicodedata

from .demae_area_registry import AreaRegistry
from .demae_catalog_categories import classify_restaurants
from .japan_post import areas


def _address(value):
    normalized = re.sub(r'\s+', '', unicodedata.normalize('NFKC', value))
    # Routing only: retain the original provider address in displayed records.
    # Hamamatsu confirms all former Naka ward became Chuo on 2024-01-01:
    # https://www.city.hamamatsu.shizuoka.jp/ksh/d/sj-1.html
    old = '静岡県浜松市中区'
    if normalized.startswith(old):
        normalized = '静岡県浜松市中央区' + normalized[len(old):]
    return normalized


class DirectoryCategories:
    """Expose known category labels, never payment or delivery capabilities.

    Classification intentionally uses the existing exact-label policy. Unknown
    provider genres remain unmapped, rather than being made orderable.
    """
    def __init__(self, catalogs, registry, postal_database):
        if not isinstance(registry, AreaRegistry):
            raise ValueError('Directory categories require a validated area registry')
        self.registry = registry
        locations = {}
        for prefecture in areas(postal_database):
            for city in areas(postal_database, prefecture['id']):
                locations[city['id']] = (prefecture['id'], _address(prefecture['name'] + city['name']))
        rows = {}
        seen = set()
        for document in catalogs:
            identity = document.get('prefecture_id')
            if (document.get('provider') != 'hotpepper' or not isinstance(identity, str)
                    or not re.fullmatch(r'JP-(0[1-9]|[1-3][0-9]|4[0-7])', identity)
                    or identity in rows):
                raise ValueError('Invalid or duplicate Hot Pepper prefecture catalog')
            restaurants = document.get('restaurants')
            if not isinstance(restaurants, list) or len(restaurants) > 1000:
                raise ValueError('Invalid or oversized directory snapshot')
            rows[identity] = []
            for restaurant in restaurants:
                identifier = restaurant.get('id') if isinstance(restaurant, dict) else None
                if (not isinstance(identifier, str) or not re.fullmatch(r'hotpepper:J[0-9]{9}', identifier)
                        or identifier in seen):
                    raise ValueError('Invalid or duplicate restaurant identity')
                seen.add(identifier)
                rows[identity].append(restaurant)
        self.categories = {}
        self.restaurants = {}
        for municipality, (prefecture, prefix) in locations.items():
            selected = [row for row in rows.get(prefecture, [])
                        if isinstance(row.get('address'), str) and _address(row['address']).startswith(prefix)]
            report = classify_restaurants(selected)
            codes = tuple(code for code, group in report['categories'].items() if group['restaurant_ids'])
            if codes:
                self.categories[municipality] = codes
                by_id = {row['id']: dict(row) for row in selected}
                self.restaurants[municipality] = {
                    code: tuple(by_id[identifier] for identifier in report['categories'][code]['restaurant_ids'])
                    for code in codes}

    def codes_for(self, area_code):
        area = self.registry.resolve(area_code)
        if area is None:
            return ()
        return self.categories.get(area['municipality'], ())

    def restaurants_for(self, area_code, category_code):
        area = self.registry.resolve(area_code)
        if area is None:
            return ()
        rows = self.restaurants.get(area['municipality'], {}).get(category_code, ())
        return tuple(dict(row) for row in rows)
