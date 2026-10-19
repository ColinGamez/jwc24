"""Nationwide index of exact-branch menu evidence; missing evidence stays missing."""
from copy import deepcopy
from datetime import datetime, timezone
import re

from .demae_menu import menu_for, basket_plan
from .demae_restaurant_links import provider_shop_url


class MenuDirectory:
    def __init__(self, catalogs, reviews, observations):
        self.restaurants, self.prefectures = {}, {}
        seen_prefectures = set()
        for catalog in catalogs:
            prefecture = catalog.get('prefecture_id')
            if (catalog.get('provider') != 'hotpepper' or not isinstance(prefecture, str)
                    or not re.fullmatch(r'JP-(0[1-9]|[1-3][0-9]|4[0-7])', prefecture)
                    or prefecture in seen_prefectures):
                raise ValueError('Invalid or duplicate menu source prefecture')
            seen_prefectures.add(prefecture)
            self.prefectures[prefecture] = []
            for row in catalog['restaurants']:
                identifier = row.get('id')
                if (not isinstance(identifier, str) or not re.fullmatch(r'hotpepper:J[0-9]{9}', identifier)
                        or identifier in self.restaurants):
                    raise ValueError('Invalid or duplicate menu restaurant identity')
                self.restaurants[identifier] = deepcopy(row)
                self.prefectures[prefecture].append(identifier)
        self.reviews = self._index(reviews, 'review')
        self.observations = self._index(observations, 'observation')
        urls = [provider_shop_url(review.get('provider_url')) for review in self.reviews.values()]
        if len(set(urls)) != len(urls):
            raise ValueError('One provider branch cannot represent multiple restaurants')

    def _index(self, rows, kind):
        result = {}
        for row in rows:
            identifier = row.get('restaurant_id') if isinstance(row, dict) else None
            if identifier not in self.restaurants or identifier in result:
                raise ValueError(f'Unknown or duplicate menu {kind} restaurant')
            result[identifier] = deepcopy(row)
        return result

    def menu(self, identifier, *, now=None):
        if identifier not in self.restaurants:
            raise ValueError('Unknown catalog restaurant')
        if identifier not in self.reviews:
            raise ValueError('Missing reviewed provider branch')
        if identifier not in self.observations:
            raise ValueError('Missing branch-specific menu observation')
        # Recheck timestamps on every use, even in a long-lived server.
        return menu_for(self.restaurants[identifier], self.reviews[identifier],
                        self.observations[identifier], now=now)

    def plan(self, identifier, selections, *, now=None):
        return basket_plan(self.menu(identifier, now=now), selections, now=now)

    def menu_page(self, identifier, *, page=1, page_size=6, category=None, now=None):
        """Return a bounded read-only page, revalidating evidence on every call.

        Categories and item IDs retain source identity across page boundaries.
        This is a backend view, not an implementation of the native Wii UI.
        """
        if (type(page) is not int or page < 1 or type(page_size) is not int
                or not 1 <= page_size <= 20):
            raise ValueError('Invalid menu page or page size')
        menu = self.menu(identifier, now=now)
        categories = list(dict.fromkeys(item['category'] for item in menu['items']))
        if category is not None and (not isinstance(category, str) or category not in categories):
            raise ValueError('Unknown menu category')
        rows = [item for item in menu['items'] if category is None or item['category'] == category]
        total_pages = (len(rows)+page_size-1)//page_size
        if page > total_pages:
            raise ValueError('Menu page is out of range')
        start = (page-1)*page_size
        return {**menu, 'items': rows[start:start+page_size],
                'categories': categories, 'category': category,
                'page': page, 'page_size': page_size, 'total_pages': total_pages,
                'total_items': len(rows), 'previous_page': page-1 if page > 1 else None,
                'next_page': page+1 if page < total_pages else None}

    def coverage(self, *, now=None):
        now = now or datetime.now(timezone.utc)
        regions, restaurants = [], []
        for prefecture, identifiers in sorted(self.prefectures.items()):
            ready = items = compatible = 0
            for identifier in identifiers:
                issues = []
                if identifier not in self.reviews:
                    issues.append('missing_branch_review')
                if identifier not in self.observations:
                    issues.append('missing_menu_observation')
                if not issues:
                    try:
                        menu = self.menu(identifier, now=now)
                    except ValueError as error:
                        issues.append(str(error))
                    else:
                        ready += 1
                        items += len(menu['items'])
                        compatible += int(menu['cp932_labels'])
                restaurants.append({'restaurant_id': identifier, 'prefecture': prefecture,
                                    'menu_plan_ready': not issues, 'issues': issues})
            regions.append({'prefecture': prefecture, 'catalog_restaurants': len(identifiers),
                            'menu_plan_restaurants': ready, 'observed_menu_items': items,
                            'cp932_menu_restaurants': compatible})
        return {'prefectures': regions, 'restaurants': restaurants,
                'menu_plan_restaurants': sum(region['menu_plan_restaurants'] for region in regions),
                'observed_menu_items': sum(region['observed_menu_items'] for region in regions),
                'cp932_menu_restaurants': sum(region['cp932_menu_restaurants'] for region in regions),
                'native_menu_integrated': False, 'ordering_supported': False}
