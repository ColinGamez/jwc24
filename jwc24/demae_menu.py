"""Branch-bound menu observations and shopping plans; never provider orders."""
from datetime import datetime, timezone
import hashlib
import re

from .demae_restaurant_links import resolve_reviewed_link, provider_shop_url


def _recent(value, now):
    try:
        observed = datetime.fromisoformat(value)
        if observed.tzinfo is None or not 0 <= (now-observed).total_seconds() <= 86400:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError('Menu observation must be timezone-aware and at most 24 hours old') from None


def menu_for(restaurant, review, observation, *, now=None):
    """Require reviewed branch identity before attaching observed menu facts."""
    now = now or datetime.now(timezone.utc)
    context = resolve_reviewed_link(restaurant, review, now=now)
    if not isinstance(observation, dict) or observation.get('restaurant_id') != context['restaurant_id']:
        raise ValueError('Menu restaurant identity mismatch')
    if provider_shop_url(observation.get('source_url')) != context['provider_url']:
        raise ValueError('Menu belongs to a different provider branch')
    _recent(observation.get('observed_at'), now)
    rows = observation.get('items')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
        raise ValueError('Expected bounded observed menu items')
    items, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid observed menu item')
        name, category, price = row.get('name'), row.get('category'), row.get('listed_price_yen')
        for value in (name, category):
            if (not isinstance(value, str) or not value.strip() or len(value) > 128
                    or re.search(r'[\x00-\x1f\x7f]', value)):
                raise ValueError('Invalid observed menu label')
            value.encode('utf-8', errors='strict')
        try:
            name.encode('cp932', errors='strict')
            category.encode('cp932', errors='strict')
            cp932_labels = True
        except UnicodeEncodeError:
            cp932_labels = False
        if type(price) is not int or not 1 <= price <= 1_000_000:
            raise ValueError('Invalid listed item price')
        # Local identity is explicitly distinct from an unknown provider SKU.
        key = hashlib.sha256((context['provider_url']+'\0'+category+'\0'+name).encode()).hexdigest()[:24]
        if key in seen:
            raise ValueError('Duplicate observed menu identity')
        seen.add(key)
        if type(row.get('options_observed')) is not bool:
            raise ValueError('Menu option evidence must be explicit')
        items.append({'id': 'observed:'+key, 'name': name, 'category': category,
            'listed_price_yen': price, 'provider_item_id': None,
            'cp932_labels': cp932_labels,
            'options_observed': row['options_observed']})
    return {'restaurant': context, 'observed_at': observation['observed_at'],
        'source_url': context['provider_url'], 'items': items,
        'cp932_labels': all(item['cp932_labels'] for item in items),
        'complete_menu': False, 'delivery_available': None,
        'ordering_supported': False, 'price_scope': 'listed item prices; delivery fees and checkout changes excluded'}


def basket_plan(menu, selections, *, now=None):
    """Calculate a local plan only; provider checkout must reselect all items."""
    now = now or datetime.now(timezone.utc)
    _recent(menu.get('observed_at'), now)
    if not isinstance(selections, list) or not 1 <= len(selections) <= 50:
        raise ValueError('Expected a bounded nonempty basket')
    by_id = {item['id']: item for item in menu['items']}
    seen, lines = set(), []
    for selection in selections:
        if not isinstance(selection, dict) or set(selection) != {'item_id', 'quantity'}:
            raise ValueError('Invalid basket selection')
        identifier, quantity = selection['item_id'], selection['quantity']
        if (not isinstance(identifier, str) or identifier not in by_id or identifier in seen
                or type(quantity) is not int or not 1 <= quantity <= 20):
            raise ValueError('Unknown, repeated or invalid basket item')
        seen.add(identifier)
        item = by_id[identifier]
        lines.append({'item_id': identifier, 'name': item['name'], 'quantity': quantity,
            'listed_unit_price_yen': item['listed_price_yen'],
            'listed_line_price_yen': quantity*item['listed_price_yen']})
    return {'restaurant': dict(menu['restaurant']), 'lines': lines,
        'observed_at': menu['observed_at'],
        'listed_items_subtotal_yen': sum(line['listed_line_price_yen'] for line in lines),
        'checkout_total_yen': None, 'delivery_available': None,
        'provider_basket_transferred': False, 'ordering_supported': False,
        'phone_action': 'Reselect these items and confirm options and final charges on the provider page'}
