"""Explicit gates for retained local Wii no Ma integration fixtures.

These fixtures are existing private experiments, not public baseline data or
proof of original service behavior. Only missing primary inputs cause a skip.
When they exist, corrupt catalogs or missing asserted assets must still fail.
"""
from functools import wraps
import os
from pathlib import Path
import stat
import unittest
from unittest.mock import patch


PRIVATE_INPUTS = {
    'theater': ('theater catalog', Path('private/wii_no_ma/theater/catalog.json'), 'JWC24_THEATER_CATALOG'),
    'shop': ('shop catalog', Path('private/wii_no_ma/shop/rakuten.json'), 'JWC24_RAKUTEN_CATALOG'),
    'miis': ('Mii roster', Path('private/wii_no_ma/miis/roster.json'), 'JWC24_MII_ROSTER'),
    'rooms': ('special-room catalog', Path('private/wii_no_ma/special/rooms.json'), None),
    'bandwidth_movie': ('bandwidth-test movie', Path('private/wii_no_ma/theater/assets/movies/c8/2-H.mov'), None),
}


def requires_private_wii_no_ma(*names):
    """Skip absent private inputs; retain assertions and pin matching catalog paths."""
    inputs = tuple(PRIVATE_INPUTS[name] for name in names)

    def decorate(function):
        @wraps(function)
        def run(*args, **kwargs):
            for label, path, _environment in inputs:
                try:
                    metadata = path.stat()
                except FileNotFoundError:
                    raise unittest.SkipTest(f'Private Wii no Ma {label} unavailable')
                if not stat.S_ISREG(metadata.st_mode):
                    raise AssertionError(f'Private Wii no Ma {label} is not a regular file')
            environment = {key: str(path.resolve()) for _label, path, key in inputs if key}
            with patch.dict(os.environ, environment):
                return function(*args, **kwargs)
        return run
    return decorate


def with_synthetic_wii_no_ma_catalogs(function):
    """Isolate XML-shape unit tests from local data; no native/content claim.

    This fixture exists only inside the test call. It is not a published menu,
    product, movie, licensed media sample or restored original-channel asset.
    """
    @wraps(function)
    def run(*args, **kwargs):
        movies = [{'movie_id': 1, 'category_id': 11001, 'title': 'Synthetic movie',
                   'length_seconds': 30, 'staff': 'Synthetic credit'}]
        products = [{'item_code': 'synthetic:1', 'name': 'Synthetic product',
                     'price_yen': 1, 'review_count': 0}]
        with patch('jwc24.wii_no_ma._theater_movies', return_value=movies), \
             patch('jwc24.wii_no_ma._shop_products', return_value=products), \
             patch('jwc24.wii_no_ma._all_miis', return_value=[]), \
             patch('jwc24.wii_no_ma._special_rooms', return_value=[]):
            return function(*args, **kwargs)
    return run
