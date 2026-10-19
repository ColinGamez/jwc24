"""Explicit, read-only Hot Pepper Gourmet catalog fetches; no ordering API."""
from __future__ import annotations

import json
import math
import os
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ENDPOINT = 'https://webservice.recruit.co.jp/hotpepper/gourmet/v1/'
KEY_ENV = 'JWC24_HOTPEPPER_API_KEY'
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
ATTRIBUTION = {
    'text': 'Powered by ホットペッパーグルメ Webサービス',
    'url': 'http://webservice.recruit.co.jp/',
    'image_credit': '画像提供：ホットペッパー グルメ',
    'guideline_url': 'https://webservice.recruit.co.jp/doc/hotpepper/guideline.html',
}


class HotPepperError(ValueError):
    """A sanitized provider failure, without credential-bearing request URLs."""


def _text(value):
    return value.strip() if isinstance(value, str) and len(value) <= 4096 else None


def _genre_code(value):
    return value if isinstance(value, str) and re.fullmatch(r'G[0-9]{3}', value) else None


def _url(value):
    value = _text(value)
    if not value:
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme in ('https', 'http') and parts.hostname and not parts.username:
            return value
    except ValueError:
        pass
    return None


def _coordinate(value, limit):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and abs(number) <= limit else None


def normalize_response(data: bytes) -> dict[str, object]:
    """Keep public directory fields; omit contacts and all ordering assumptions."""
    if len(data) > MAX_RESPONSE_BYTES:
        raise HotPepperError('Hot Pepper response exceeds the 2 MiB limit')
    try:
        document = json.loads(data)
    except (ValueError, UnicodeError, RecursionError):
        raise HotPepperError('Hot Pepper returned invalid JSON') from None
    results = document.get('results') if isinstance(document, dict) else None
    if not isinstance(results, dict) or results.get('error'):
        raise HotPepperError('Hot Pepper returned an API error or invalid response')
    shops = results.get('shop')
    if not isinstance(shops, list) or len(shops) > 100:
        raise HotPepperError('Hot Pepper returned an invalid restaurant list')
    restaurants = []
    seen = set()
    for shop in shops:
        if not isinstance(shop, dict):
            raise HotPepperError('Hot Pepper returned an invalid restaurant record')
        identifier = shop.get('id')
        name = _text(shop.get('name'))
        if not isinstance(identifier, str) or not re.fullmatch(r'J[0-9]{9}', identifier) or not name:
            raise HotPepperError('Hot Pepper restaurant is missing a valid ID or name')
        if identifier in seen:
            continue
        seen.add(identifier)
        def nested(*keys):
            value = shop
            for key in keys:
                value = value.get(key) if isinstance(value, dict) else None
            return value
        restaurants.append({
            'id': f'hotpepper:{identifier}', 'source_id': identifier, 'name': name,
            'address': _text(shop.get('address')),
            'genre': _text(nested('genre', 'name')),
            'genre_code': _genre_code(nested('genre', 'code')),
            'genre_catchphrase': _text(nested('genre', 'catch')),
            'sub_genre_code': _genre_code(nested('sub_genre', 'code')),
            'catchphrase': _text(shop.get('catch')),
            'logo_url': _url(shop.get('logo_image')),
            'photo_url': _url(nested('photo', 'pc', 'l')),
            'source_url': _url(nested('urls', 'pc')),
            'latitude': _coordinate(shop.get('lat'), 90),
            'longitude': _coordinate(shop.get('lng'), 180),
            'budget_description': _text(nested('budget', 'name')),
            'opening_hours_text': _text(shop.get('open')),
            'menu_items': None, 'minimum_order_yen': None,
            'delivery_available': None, 'ordering_supported': False,
        })
    pagination = {}
    for field in ('results_available', 'results_returned', 'results_start'):
        value = results.get(field)
        if value is not None:
            if isinstance(value, bool) or not str(value).isdigit():
                raise HotPepperError('Invalid provider pagination')
            pagination[field] = int(value)
    return {'schema_version': 2, 'provider': 'hotpepper', 'pagination': pagination,
            'attribution': dict(ATTRIBUTION), 'restaurants': restaurants,
            'scope': 'directory only; menus, delivery and item prices not provided'}


def fetch_catalog(keyword: str = '', *, large_area: str | None = None, start: int = 1, count: int = 100,
                  api_key: str | None = None) -> dict[str, object]:
    """Fetch one UTF-8 keyword page on explicit invocation, never per Wii request."""
    if not isinstance(keyword, str) or len(keyword) > 256 or (not keyword.strip() and large_area is None):
        raise HotPepperError('A nonempty keyword of at most 256 characters is required')
    if large_area is not None and (not isinstance(large_area, str) or not re.fullmatch(r'Z[0-9]{3}', large_area)):
        raise HotPepperError('Invalid provider large-area code')
    if type(start) is not int or start < 1 or start > 1000000:
        raise HotPepperError('Start must be an integer between 1 and 1000000')
    if type(count) is not int or not 1 <= count <= 100:
        raise HotPepperError('Count must be an integer between 1 and 100')
    key = api_key if api_key is not None else os.environ.get(KEY_ENV)
    if not isinstance(key, str) or not key.strip():
        raise HotPepperError(f'Set {KEY_ENV} before fetching Hot Pepper data')
    parameters = {'key': key.strip(), 'start': start, 'count': count, 'format': 'json'}
    if keyword.strip():
        parameters['keyword'] = keyword.strip()
    if large_area is not None:
        parameters['large_area'] = large_area
    query = urlencode(parameters)
    request = Request(ENDPOINT + '?' + query, headers={'User-Agent': 'JWC24-catalog-import/1.0'})
    try:
        with urlopen(request, timeout=30) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except Exception:
        # urllib errors may include the complete URL and its API key.
        raise HotPepperError('Hot Pepper request failed; check network and API configuration') from None
    catalog = normalize_response(data)
    catalog['query'] = {'keyword': keyword.strip(), 'start': start, 'count': count}
    if large_area is not None:
        catalog['query']['large_area'] = large_area
    return catalog
